# Redis Caching for CI/CD Agents

**Purpose**: Intelligent caching layer that eliminates redundant LLM inference calls for repeated patterns, reducing both latency and costs.

## Overview

The Redis caching system provides production-ready performance optimization by caching AI agent decisions. When identical or similar tasks are requested, cached results are returned instantly instead of making expensive LLM inference calls.

### Benefits

✅ **Latency Reduction**: Cache hits return in <10ms vs 5-10s for LLM inference
✅ **Cost Optimization**: $0 for cached results vs API costs for cloud LLM calls
✅ **Deterministic Behavior**: Consistent results for identical inputs
✅ **Production Ready**: Confidence thresholds ensure only reliable decisions are cached

## Architecture

```
User Request
    ↓
Agent receives input (commit, test status, metrics)
    ↓
Generate cache key (SHA256 hash of input)
    ↓
Check Redis cache
    ├─ HIT  → Return cached result (saved 5-10s latency)
    └─ MISS → Run LLM inference
              ↓
              Calculate confidence score
              ↓
              Cache result if confidence ≥ threshold
              ↓
              Return result
```

## Configuration

### Environment Variables

```bash
# Redis connection
export REDIS_URL="redis://localhost:6379/0"

# Cache behavior
export AGENT_CACHE_ENABLED="true"              # Enable/disable caching
export AGENT_CACHE_CONFIDENCE_THRESHOLD="0.8"  # Minimum confidence to cache (0.0-1.0)
export AGENT_CACHE_TTL_DAYS="7"               # Cache expiration in days
```

### Quick Start

**Option 1: Docker Redis**
```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

**Option 2: Native Redis**
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis
```

**Install Python Redis Client**
```bash
cd /opt/motia
./venv/bin/pip install redis
```

## Cache Key Generation

Cache keys are deterministically generated from input data using SHA256 hashing:

```python
# Example: BuildAgent cache key
input_data = {
    'repo': 'billionmail',
    'commit': 'abc123',
    'branch': 'main',
    'files_changed': ['api.py', 'models.py'],
    'lines_changed': '+45,-12'
}

# Generated cache key
# agent:build:a3f5e8d9c2b1...  (SHA256 hash)
```

**Key Properties**:
- Deterministic: Same input → same key
- Collision-resistant: Different inputs → different keys
- Namespace isolation: Each agent has separate cache space

## Confidence-Based Caching

Only high-confidence decisions are cached to maintain reliability.

### BuildAgent Confidence Scoring

```python
# High confidence (1.0) - Always cache
- Dockerfile or docker-compose.yml changes
- Clear should_build = True decisions

# Medium confidence (0.9) - Cache
- should_build = False (skip build decisions)
- Standard code changes with clear patterns
```

### TestAgent Confidence Scoring

```python
# High confidence (0.95) - Always cache
- File patterns match known types (api, models, auth, config, ui)
- Standard test selection patterns

# Medium confidence (0.75) - May cache
- Unknown file patterns
- Unusual change combinations
```

### DeployAgent Confidence Scoring

```python
# High confidence (0.9) - Always cache
- should_deploy = True with clear metrics

# Medium confidence (0.85) - Cache
- should_deploy = False (block deployment)

# Reduced confidence (0.72-0.68) - Selective caching
- High-risk deployments (confidence * 0.8)
- Critical risk level changes
```

### MonitorAgent Confidence Scoring

```python
# High confidence (0.95) - Always cache
- 'normal' alert level (healthy deployment)
- 'critical' alert level (clear rollback needed)

# Medium confidence (0.85) - Cache
- General health assessments

# Low confidence (0.75) - May not cache
- 'warning' alert level (borderline states)
```

## Cache Hit Rate Tracking

Each agent tracks cache performance:

```python
from redis_cache import AgentCache

cache = AgentCache()
stats = cache.get_cache_stats('build')

# Example output:
{
    'hits': 145,
    'misses': 78,
    'total': 223,
    'hit_rate': 65.0,  # 65% cache hit rate
    'enabled': True
}
```

### Expected Hit Rates

**Development/Testing**: 40-60% (frequent unique changes)
**Staging**: 50-70% (repeated testing patterns)
**Production**: 60-80% (stable change patterns)

## Cache Management

### View Cache Statistics

```python
# Per-agent statistics
from redis_cache import AgentCache

cache = AgentCache()

print("BuildAgent:", cache.get_cache_stats('build'))
print("TestAgent:", cache.get_cache_stats('test'))
print("DeployAgent:", cache.get_cache_stats('deploy'))
print("MonitorAgent:", cache.get_cache_stats('monitor'))
```

### Clear Agent Cache

```python
# Clear specific agent's cache
cache.clear_agent_cache('build')  # Returns number of keys deleted

# Clear all agent caches
cache.clear_all_cache()  # Returns total keys deleted
```

### Cache Invalidation Triggers

**Automatic Expiration**: TTL-based (default 7 days)

**Manual Invalidation** (when needed):
- System configuration changes
- AI model updates
- Agent behavior modifications
- Risk assessment threshold changes

```bash
# Clear cache after configuration changes
cd /opt/motia/agents/shared
../../venv/bin/python -c "
from redis_cache import AgentCache
cache = AgentCache()
cache.clear_all_cache()
print('Cache cleared')
"
```

## Performance Metrics

### Latency Comparison

| Operation | Without Cache | With Cache (Hit) | Improvement |
|-----------|---------------|------------------|-------------|
| BuildAgent | 5-10s | <10ms | **99.8%** faster |
| TestAgent | 6-8s | <10ms | **99.8%** faster |
| DeployAgent | 5-10s | <10ms | **99.9%** faster |
| MonitorAgent | 3-5s | <10ms | **99.7%** faster |

### Cost Savings (Ollama Cloud)

Assuming 1000 CI/CD runs per month with 60% cache hit rate:

**Without Caching**:
```
1000 runs × $0.0002 per inference × 4 agents = $0.80/month
```

**With Caching (60% hit rate)**:
```
400 cache misses × $0.0002 × 4 agents = $0.32/month
Savings: $0.48/month (60% reduction)
```

At scale (10,000 runs/month):
```
Without: $8.00/month
With: $3.20/month
Savings: $4.80/month (60% reduction)
```

## Integration Examples

### Example 1: BuildAgent with Caching

```python
from agent import BuildAgent

# Initialize agent (cache automatically enabled if Redis available)
agent = BuildAgent()

commit_data = {
    'repo': 'billionmail',
    'commit': 'abc123',
    'files_changed': ['api.py', 'models.py']
}

# First call: Cache MISS → LLM inference (5-10s)
result = agent.analyze_commit_sync(commit_data)
print(result.should_build)  # True

# Second call with same data: Cache HIT → instant (<10ms)
result = agent.analyze_commit_sync(commit_data)
print(result.should_build)  # True (from cache)
```

**Console Output**:
```
[BuildAgent] Using Local Ollama | Cost: $0 | Latency: 5-10s
[BuildAgent] Cache enabled | Confidence threshold: 0.8
[AgentCache] Cache MISS for build: a3f5e8d9c2b1...
[AgentCache] Cached result for build (confidence: 1.00)

# Second call:
[AgentCache] Cache HIT for build: a3f5e8d9c2b1...
[BuildAgent] ✨ Using cached decision (saved ~5-10s latency)
```

### Example 2: Testing Cache Behavior

```bash
cd /opt/motia/agents/shared
../../venv/bin/python -c "
from redis_cache import AgentCache

cache = AgentCache()

# Test data
input1 = {'repo': 'test', 'commit': 'abc123', 'files': ['api.py']}
result1 = {'should_build': True, 'strategy': 'cache'}

# Cache with high confidence
cache.cache_result('build', input1, result1, confidence=0.95)
print('✅ Cached with high confidence')

# Retrieve cached result
cached = cache.get_cached_result('build', input1)
print(f'✅ Retrieved: {cached[\"result\"]}')

# Try low confidence (won't cache)
input2 = {'repo': 'test', 'commit': 'xyz789', 'files': ['README.md']}
result2 = {'should_build': False, 'strategy': 'skip'}

cache.cache_result('build', input2, result2, confidence=0.5)
print('⚠️  Low confidence - not cached')

# Statistics
stats = cache.get_cache_stats('build')
print(f'📊 Hit rate: {stats[\"hit_rate\"]:.1f}%')
"
```

## Monitoring & Observability

### Redis Monitoring

```bash
# Connect to Redis CLI
redis-cli

# View all agent cache keys
KEYS agent:*

# View specific agent's keys
KEYS agent:build:*

# Check key TTL
TTL agent:build:a3f5e8d9c2b1...

# View key value
GET agent:build:a3f5e8d9c2b1...

# Cache statistics
INFO stats
```

### Prometheus Metrics (Future Enhancement)

```python
# Potential metrics to track
agent_cache_hit_total{agent="build"}
agent_cache_miss_total{agent="build"}
agent_cache_hit_rate{agent="build"}
agent_cache_latency_seconds{agent="build", result="hit"}
agent_cache_latency_seconds{agent="build", result="miss"}
```

## Troubleshooting

### Redis Not Available

**Symptom**: Agents work but show cache disabled warnings

**Fix**:
```bash
# Check if Redis is running
redis-cli ping
# Expected: PONG

# If not running, start Redis
docker start redis
# or
sudo systemctl start redis-server
```

### Low Cache Hit Rate (<30%)

**Possible Causes**:
1. Highly diverse change patterns (normal for active development)
2. TTL too short (increase `AGENT_CACHE_TTL_DAYS`)
3. Confidence threshold too high (lower `AGENT_CACHE_CONFIDENCE_THRESHOLD`)

**Analysis**:
```python
# Check what's being cached
from redis_cache import AgentCache
cache = AgentCache()

# View cache statistics
for agent in ['build', 'test', 'deploy', 'monitor']:
    stats = cache.get_cache_stats(agent)
    print(f"{agent}: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate']:.1f}% hit rate")
```

### Redis Connection Errors

**Symptom**: Cache initialization fails with connection errors

**Fix**:
```bash
# Check Redis is accessible
telnet localhost 6379

# Check Redis logs
docker logs redis
# or
sudo journalctl -u redis-server

# Verify REDIS_URL environment variable
echo $REDIS_URL
```

### Cache Poisoning Prevention

The system prevents cache poisoning through:

1. **Confidence Thresholds**: Only high-confidence results cached
2. **TTL Expiration**: Automatic cache invalidation after 7 days
3. **Deterministic Keys**: SHA256 prevents key collision attacks
4. **Namespace Isolation**: Each agent has separate cache space

## Production Deployment

### Redis Configuration

**Production Redis Setup**:
```yaml
# redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru  # Evict least recently used keys
save ""  # Disable RDB snapshots (optional - cache is ephemeral)
appendonly no  # Disable AOF (optional - cache is ephemeral)
```

**Docker Compose**:
```yaml
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  redis-data:
```

### High Availability (Optional)

For critical production deployments:

```yaml
# Redis Sentinel for HA
services:
  redis-master:
    image: redis:alpine

  redis-replica:
    image: redis:alpine
    command: redis-server --replicaof redis-master 6379

  redis-sentinel:
    image: redis:alpine
    command: redis-sentinel /etc/sentinel.conf
```

## Best Practices

1. **Monitor Hit Rates**: Track cache effectiveness per agent
2. **Tune Confidence Thresholds**: Balance caching vs reliability
3. **Manage TTL**: Adjust based on change frequency
4. **Clear on Config Changes**: Invalidate cache after system updates
5. **Use Redis Persistence** (optional): Enable RDB/AOF for cache persistence
6. **Set Memory Limits**: Configure `maxmemory` to prevent Redis OOM
7. **Monitor Redis Health**: Set up alerts for Redis availability

## Summary

Redis caching provides **significant performance and cost benefits** with minimal operational overhead:

- ✅ **99%+ latency reduction** for cache hits
- ✅ **60-80% cost savings** for cloud LLM usage
- ✅ **Production-ready** confidence-based caching
- ✅ **Zero code changes** required in agent logic
- ✅ **Automatic fallback** if Redis unavailable
- ✅ **Comprehensive monitoring** and statistics

The system is designed to be **safe, efficient, and transparent**, providing instant performance improvements while maintaining the reliability of AI-driven decisions.
