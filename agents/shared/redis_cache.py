"""
Redis-based caching for AI agent decisions

Provides intelligent caching with:
- Input hashing for deterministic cache keys
- Confidence-based caching (only cache high-confidence results)
- TTL management for cache freshness
- Cache hit rate tracking and analytics
- Distributed caching support
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("redis package not installed - caching disabled")


logger = logging.getLogger(__name__)


class AgentCache:
    """
    Redis-based caching layer for AI agent decisions

    Caches successful agent decisions to avoid redundant LLM inference calls
    for identical or similar inputs.

    Environment Variables:
    - REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
    - AGENT_CACHE_ENABLED: Enable/disable caching (default: true)
    - AGENT_CACHE_CONFIDENCE_THRESHOLD: Minimum confidence to cache (default: 0.8)
    - AGENT_CACHE_TTL_DAYS: Cache expiration in days (default: 7)
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        ttl_days: Optional[int] = None,
        enabled: Optional[bool] = None
    ):
        """
        Initialize AgentCache

        Args:
            redis_url: Redis connection URL (defaults to env REDIS_URL)
            confidence_threshold: Minimum confidence to cache (defaults to env or 0.8)
            ttl_days: Cache TTL in days (defaults to env or 7)
            enabled: Enable caching (defaults to env or True)
        """
        # Configuration from environment or defaults
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.confidence_threshold = confidence_threshold or float(os.getenv('AGENT_CACHE_CONFIDENCE_THRESHOLD', '0.8'))
        ttl_days = ttl_days or int(os.getenv('AGENT_CACHE_TTL_DAYS', '7'))
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self.enabled = enabled if enabled is not None else os.getenv('AGENT_CACHE_ENABLED', 'true').lower() == 'true'

        # Initialize Redis client if available and enabled
        self.redis_client = None
        if REDIS_AVAILABLE and self.enabled:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"[AgentCache] Connected to Redis: {self.redis_url}")
                logger.info(f"[AgentCache] Confidence threshold: {self.confidence_threshold}")
                logger.info(f"[AgentCache] TTL: {ttl_days} days")
            except Exception as e:
                logger.warning(f"[AgentCache] Redis connection failed: {e} - caching disabled")
                self.redis_client = None
                self.enabled = False
        else:
            if not REDIS_AVAILABLE:
                logger.warning("[AgentCache] redis package not installed - caching disabled")
            elif not self.enabled:
                logger.info("[AgentCache] Caching disabled via AGENT_CACHE_ENABLED=false")

    def generate_cache_key(self, agent_name: str, input_data: Dict[str, Any]) -> str:
        """
        Generate deterministic cache key from agent name and input data

        Args:
            agent_name: Name of the agent (build, test, deploy, monitor)
            input_data: Input data dictionary to hash

        Returns:
            Cache key string
        """
        # Sort keys for deterministic hashing
        input_str = json.dumps(input_data, sort_keys=True)
        hash_digest = hashlib.sha256(input_str.encode()).hexdigest()
        return f"agent:{agent_name}:{hash_digest}"

    def get_cached_result(self, agent_name: str, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached result if exists

        Args:
            agent_name: Name of the agent
            input_data: Input data to generate cache key

        Returns:
            Cached result dictionary or None if cache miss
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            cache_key = self.generate_cache_key(agent_name, input_data)
            cached = self.redis_client.get(cache_key)

            if cached:
                result = json.loads(cached)
                # Increment hit counter
                self.redis_client.incr(f"cache:hits:{agent_name}")
                logger.info(f"[AgentCache] Cache HIT for {agent_name}: {cache_key[:16]}...")
                return result
            else:
                # Increment miss counter
                self.redis_client.incr(f"cache:misses:{agent_name}")
                logger.info(f"[AgentCache] Cache MISS for {agent_name}: {cache_key[:16]}...")
                return None

        except Exception as e:
            logger.warning(f"[AgentCache] Cache retrieval error: {e}")
            return None

    def cache_result(
        self,
        agent_name: str,
        input_data: Dict[str, Any],
        result: Dict[str, Any],
        confidence: float
    ) -> bool:
        """
        Cache result if confidence threshold is met

        Args:
            agent_name: Name of the agent
            input_data: Input data to generate cache key
            result: Result dictionary to cache
            confidence: Confidence score (0.0-1.0)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        # Only cache high-confidence results
        if confidence < self.confidence_threshold:
            logger.debug(f"[AgentCache] Skipping cache (confidence {confidence:.2f} < {self.confidence_threshold})")
            return False

        try:
            cache_key = self.generate_cache_key(agent_name, input_data)

            # Add metadata
            cache_data = {
                'result': result,
                'confidence': confidence,
                'cached_at': datetime.now().isoformat(),
                'agent': agent_name
            }

            # Store with TTL
            self.redis_client.setex(
                cache_key,
                self.ttl_seconds,
                json.dumps(cache_data)
            )

            logger.info(f"[AgentCache] Cached result for {agent_name} (confidence: {confidence:.2f})")
            return True

        except Exception as e:
            logger.warning(f"[AgentCache] Cache storage error: {e}")
            return False

    def get_cache_stats(self, agent_name: str) -> Dict[str, Any]:
        """
        Get cache hit rate statistics for agent

        Args:
            agent_name: Name of the agent

        Returns:
            Statistics dictionary with hits, misses, total, hit_rate
        """
        if not self.enabled or not self.redis_client:
            return {
                'hits': 0,
                'misses': 0,
                'total': 0,
                'hit_rate': 0.0,
                'enabled': False
            }

        try:
            hits = int(self.redis_client.get(f"cache:hits:{agent_name}") or 0)
            misses = int(self.redis_client.get(f"cache:misses:{agent_name}") or 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0.0

            return {
                'hits': hits,
                'misses': misses,
                'total': total,
                'hit_rate': hit_rate,
                'enabled': True
            }
        except Exception as e:
            logger.warning(f"[AgentCache] Stats retrieval error: {e}")
            return {
                'hits': 0,
                'misses': 0,
                'total': 0,
                'hit_rate': 0.0,
                'enabled': False,
                'error': str(e)
            }

    def clear_agent_cache(self, agent_name: str) -> int:
        """
        Clear all cached results for specific agent

        Args:
            agent_name: Name of the agent

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis_client:
            return 0

        try:
            pattern = f"agent:{agent_name}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"[AgentCache] Cleared {deleted} cached results for {agent_name}")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"[AgentCache] Cache clear error: {e}")
            return 0

    def clear_all_cache(self) -> int:
        """
        Clear all agent cache entries

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis_client:
            return 0

        try:
            pattern = "agent:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"[AgentCache] Cleared {deleted} total cached results")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"[AgentCache] Cache clear error: {e}")
            return 0


def cached_agent_method(agent_name: str, confidence_calculator: Optional[Callable] = None):
    """
    Decorator to add caching to agent methods

    Args:
        agent_name: Name of the agent (build, test, deploy, monitor)
        confidence_calculator: Optional function to calculate confidence from result
                              If None, defaults to 1.0 (high confidence)

    Usage:
        @cached_agent_method('build', lambda result: 1.0 if result.should_build else 0.9)
        async def analyze_commit(self, commit_data, session_id=None):
            # ... method implementation
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Check if agent has cache instance
            if not hasattr(self, 'cache') or not self.cache:
                # No cache - call original method
                return await func(self, *args, **kwargs)

            # Generate input data for cache key from args/kwargs
            # Assume first positional arg is the input data dict
            input_data = args[0] if args else {}

            # Try to get cached result
            cached = self.cache.get_cached_result(agent_name, input_data)
            if cached:
                # Extract result from cache metadata
                result_data = cached.get('result', cached)
                # Reconstruct result object (assumes Pydantic model)
                result_class = func.__annotations__.get('return')
                if result_class:
                    return result_class(**result_data)
                return result_data

            # Cache miss - call original method
            result = await func(self, *args, **kwargs)

            # Calculate confidence
            if confidence_calculator:
                confidence = confidence_calculator(result)
            else:
                confidence = 1.0  # Default high confidence

            # Cache the result
            result_dict = result.dict() if hasattr(result, 'dict') else result
            self.cache.cache_result(agent_name, input_data, result_dict, confidence)

            return result

        return wrapper
    return decorator


# Global cache instance (optional - can be instantiated per-agent)
_global_cache = None

def get_global_cache() -> AgentCache:
    """Get or create global cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = AgentCache()
    return _global_cache


if __name__ == '__main__':
    """Test AgentCache functionality"""

    print("=== AgentCache Test ===\n")

    # Initialize cache
    cache = AgentCache()
    print(f"Cache enabled: {cache.enabled}")
    print(f"Confidence threshold: {cache.confidence_threshold}")
    print()

    if not cache.enabled:
        print("⚠️  Cache disabled - install redis package and start Redis server")
        print("   pip install redis")
        print("   docker run -d -p 6379:6379 redis:alpine")
        exit(0)

    # Test data
    test_input = {
        'repo': 'billionmail',
        'commit': 'abc123',
        'files_changed': ['api.py', 'models.py']
    }

    test_result = {
        'should_build': True,
        'strategy': 'cache',
        'estimated_time': 60
    }

    print("1. Testing cache miss...")
    cached = cache.get_cached_result('build', test_input)
    print(f"   Result: {cached}")
    print()

    print("2. Caching result with high confidence...")
    success = cache.cache_result('build', test_input, test_result, confidence=0.95)
    print(f"   Cached: {success}")
    print()

    print("3. Testing cache hit...")
    cached = cache.get_cached_result('build', test_input)
    print(f"   Result: {cached['result'] if cached else None}")
    print()

    print("4. Cache statistics...")
    stats = cache.get_cache_stats('build')
    print(f"   Hits: {stats['hits']}")
    print(f"   Misses: {stats['misses']}")
    print(f"   Hit rate: {stats['hit_rate']:.1f}%")
    print()

    print("5. Testing low confidence (should not cache)...")
    test_input2 = {
        'repo': 'test',
        'commit': 'xyz789',
        'files_changed': ['README.md']
    }
    success = cache.cache_result('build', test_input2, test_result, confidence=0.5)
    print(f"   Cached: {success} (expected False)")
    print()

    print("=== Test Complete ===")
