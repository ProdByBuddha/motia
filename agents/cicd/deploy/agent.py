"""
DeployAgent - Intelligent deployment strategy decisions

Analyzes system state and determines:
- Whether deployment is safe to proceed
- Optimal deployment strategy (blue-green, canary, rolling)
- Rollback configuration and health check settings
- Deployment risk assessment
"""

import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from sns_core import CICDNotation, CICDMessage
from hybrid_ollama import get_background_ollama
from redis_cache import AgentCache


class DeployDecision(BaseModel):
    """Structured deployment decision from AI analysis"""

    should_deploy: bool = Field(description="Whether deployment should proceed")
    reason: str = Field(description="Explanation for deployment decision")
    strategy: str = Field(description="Deployment strategy: blue-green, canary, rolling, or immediate")
    rollback_enabled: bool = Field(description="Whether automatic rollback is enabled")
    health_check_duration: int = Field(description="Health check monitoring duration in seconds")
    traffic_shift: str = Field(description="Traffic shifting strategy: immediate, gradual, or percentage-based")
    risk_level: str = Field(description="Deployment risk: low, medium, high, critical")
    canary_percentage: Optional[int] = Field(default=None, description="Canary deployment percentage (5-50)")


class DeployAgent:
    """
    Intelligent deployment decision agent using Pydantic AI

    Analyzes test results, system metrics, and deployment history to determine
    the safest and most appropriate deployment strategy.
    """

    def __init__(self, model: str = None):
        """
        Initialize DeployAgent

        Args:
            model: AI model to use (defaults to hybrid Ollama - local for background)
        """
        # Use hybrid Ollama provider (automatic local Ollama for background operations)
        self.ollama_provider = get_background_ollama(model=model)
        self.model = self.ollama_provider.get_model()
        self.sns = CICDNotation()

        # Initialize Pydantic AI agent with hybrid Ollama
        self.agent = Agent(
            self.model,
            output_type=DeployDecision,
            system_prompt=self._build_system_prompt()
        )

        # Register tools
        self._register_tools()

        # Log provider stats
        stats = self.ollama_provider.get_stats()
        print(f"[DeployAgent] Using {stats['backend']} | Cost: {stats['cost']} | Latency: {stats['latency_target']}")

        # Initialize Redis cache for decision caching
        self.cache = AgentCache()
        if self.cache.enabled:
            print(f"[DeployAgent] Cache enabled | Confidence threshold: {self.cache.confidence_threshold}")

    def _build_system_prompt(self) -> str:
        """Construct system prompt for DeployAgent"""
        return '''You are an expert deployment strategist specializing in safe and reliable software deployments.

Your role is to analyze system state and determine:
1. Whether deployment is safe to proceed
2. The optimal deployment strategy
3. Rollback and monitoring configuration
4. Risk assessment and mitigation

# Deployment Decision Guidelines

## Deployment Readiness Checks

### BLOCK Deployment If:
- Tests failing (any critical test failures)
- Current production errors elevated (>1% error rate)
- Recent deployment within cooldown period (<30 minutes for critical services)
- System resource constraints (CPU >80%, Memory >90%)
- External dependencies down

### PROCEED with Caution If:
- Non-critical test failures
- Minor production warnings
- Recent deployment (30-60 minutes ago)
- Moderate resource usage (CPU 60-80%, Memory 70-90%)

### PROCEED Normally If:
- All tests passing
- Production stable (<0.1% error rate)
- No recent deployments (>60 minutes)
- Healthy resource usage (<60% CPU, <70% Memory)
- All dependencies healthy

## Deployment Strategies

### immediate (Development/Staging)
- **Use when**: Dev/staging environments, low-risk changes
- **Benefits**: Fast deployment, simple rollback
- **Risks**: No traffic management, instant full deployment
- **Recommended**: Documentation, minor fixes, dev environments

### blue-green (Recommended Default)
- **Use when**: Zero-downtime requirement, easy rollback needed
- **Benefits**: Instant rollback, no downtime, full testing before switch
- **Risks**: Requires 2x resources temporarily
- **Recommended**: Standard production deployments, feature releases

### canary (High Risk Changes)
- **Use when**: Major changes, uncertain production behavior
- **Benefits**: Gradual rollout, early detection, limited blast radius
- **Risks**: Complex monitoring, longer deployment time
- **Canary percentages**: 5% (ultra-safe), 10% (safe), 25% (moderate), 50% (aggressive)
- **Recommended**: Database migrations, API changes, architecture updates

### rolling (Microservices)
- **Use when**: Multiple instance deployments, gradual updates
- **Benefits**: Resource efficient, gradual rollout
- **Risks**: Mixed versions running simultaneously
- **Recommended**: Stateless services, container orchestration

## Health Check Configuration

### Duration by Risk Level
- **Low risk**: 60s monitoring, 3 health checks
- **Medium risk**: 300s (5min) monitoring, 5 health checks
- **High risk**: 600s (10min) monitoring, 10 health checks
- **Critical**: 1800s (30min) monitoring, 20 health checks

### Health Check Metrics
- HTTP endpoint: /health or /api/health
- Response time: <200ms warning, <500ms acceptable
- Error rate: <0.1% good, <1% acceptable, >1% rollback
- Memory: <70% good, <85% acceptable, >90% rollback
- CPU: <60% good, <75% acceptable, >85% rollback

## Traffic Shifting Strategies

### immediate
- Switch 100% traffic instantly
- Use for: Blue-green deployments, staging

### gradual (Recommended)
- Phase 1: 10% for 5 minutes
- Phase 2: 50% for 10 minutes
- Phase 3: 100% after validation
- Use for: Canary deployments

### percentage-based
- Custom percentage (e.g., 5%, 25%, 50%)
- Monitor metrics, then decide next step
- Use for: High-risk canary deployments

## Risk Assessment Factors

### Low Risk
- Documentation changes only
- UI text/styling updates
- Non-critical bug fixes
- Configuration changes (non-breaking)

### Medium Risk
- New features (additive only)
- API endpoint additions
- Database migrations (additive)
- Dependency updates (minor versions)

### High Risk
- Breaking API changes
- Database schema modifications
- Authentication/authorization changes
- Payment/financial logic updates

### Critical Risk
- Core business logic changes
- Security updates
- Data migration/transformation
- Infrastructure changes

# Communication Protocol
Input uses sns-core notation:
img:billionmail:abc123|tests:✓|env:staging|metrics:cpu:45%,mem:60%

Output provides structured DeployDecision.
'''

    def _register_tools(self):
        """Register tools for the DeployAgent"""

        @self.agent.tool
        async def assess_test_results(ctx: RunContext[Dict[str, Any]], test_status: str) -> Dict[str, Any]:
            """Assess test results from sns-core notation"""
            # Parse test status (e.g., "✓|total:45|passed:45|time:43s")
            parts = test_status.split('|')
            success = parts[0] == '✓'

            details = {}
            for part in parts[1:]:
                if ':' in part:
                    key, value = part.split(':', 1)
                    details[key] = value

            total = int(details.get('total', '0'))
            passed = int(details.get('passed', '0'))
            coverage = (passed / total * 100) if total > 0 else 0

            return {
                'success': success,
                'total': total,
                'passed': passed,
                'failed': total - passed,
                'coverage': coverage,
                'risk': 'low' if success else 'high'
            }

        @self.agent.tool
        async def parse_system_metrics(ctx: RunContext[Dict[str, Any]], metrics: str) -> Dict[str, Any]:
            """Parse system metrics from sns-core notation"""
            # Parse metrics (e.g., "cpu:45%,mem:60%,disk:70%")
            metric_dict = {}

            for metric in metrics.split(','):
                if ':' in metric:
                    key, value = metric.split(':', 1)
                    # Remove % and convert to float
                    numeric_value = float(value.replace('%', ''))
                    metric_dict[key] = numeric_value

            # Assess health
            cpu = metric_dict.get('cpu', 0)
            memory = metric_dict.get('mem', 0)

            health_status = 'healthy'
            if cpu > 85 or memory > 90:
                health_status = 'critical'
            elif cpu > 75 or memory > 85:
                health_status = 'warning'
            elif cpu > 60 or memory > 70:
                health_status = 'moderate'

            return {
                'cpu': cpu,
                'memory': memory,
                'disk': metric_dict.get('disk', 0),
                'health_status': health_status
            }

        @self.agent.tool
        async def determine_deployment_risk(
            ctx: RunContext[Dict[str, Any]],
            files_changed: int,
            test_coverage: float,
            system_health: str
        ) -> str:
            """Determine overall deployment risk level"""
            risk_score = 0

            # File changes impact
            if files_changed > 50:
                risk_score += 3
            elif files_changed > 20:
                risk_score += 2
            elif files_changed > 5:
                risk_score += 1

            # Test coverage impact
            if test_coverage < 80:
                risk_score += 2
            elif test_coverage < 90:
                risk_score += 1

            # System health impact
            if system_health == 'critical':
                risk_score += 3
            elif system_health == 'warning':
                risk_score += 2
            elif system_health == 'moderate':
                risk_score += 1

            # Determine risk level
            if risk_score >= 6:
                return 'critical'
            elif risk_score >= 4:
                return 'high'
            elif risk_score >= 2:
                return 'medium'
            else:
                return 'low'

    async def decide_strategy(
        self,
        image_tag: str,
        test_status: str,
        environment: str,
        metrics: str,
        files_changed: int = 0,
        session_id: str = None
    ) -> DeployDecision:
        """
        Analyze system state and decide deployment strategy with Redis caching

        Args:
            image_tag: Docker image tag to deploy
            test_status: Test results in sns-core notation (e.g., "✓|total:45|passed:45")
            environment: Target environment (staging, production)
            metrics: System metrics in sns-core notation (e.g., "cpu:45%,mem:60%")
            files_changed: Number of files that changed
            session_id: Session identifier for tracking

        Returns:
            DeployDecision with structured deployment strategy
        """
        # Create cache key input
        cache_input = {
            'image_tag': image_tag,
            'test_status': test_status,
            'environment': environment,
            'metrics': metrics,
            'files_changed': files_changed
        }

        # Try to get cached result
        if self.cache and self.cache.enabled:
            cached = self.cache.get_cached_result('deploy', cache_input)
            if cached:
                result_data = cached.get('result', cached)
                print(f"[DeployAgent] ✨ Using cached deployment decision (saved ~{self.ollama_provider.get_stats()['latency_target']} latency)")
                return DeployDecision(**result_data)

        # Cache miss - run AI analysis
        # Encode input with sns-core
        encoded = f"img:{image_tag}|tests:{test_status}|env:{environment}|metrics:{metrics}"

        # Prepare context for AI
        context = {
            'image_tag': image_tag,
            'test_status': test_status,
            'environment': environment,
            'metrics': metrics,
            'files_changed': files_changed
        }

        # Run AI analysis
        result = await self.agent.run(
            f"Analyze deployment state and determine strategy: {encoded}",
            deps=context
        )

        # Calculate confidence for caching
        # High confidence for clear should_deploy decisions
        confidence = 0.9 if result.data.should_deploy else 0.85

        # Lower confidence for high-risk deployments (less predictable)
        if result.data.risk_level in ['high', 'critical']:
            confidence *= 0.8

        # Cache the result
        if self.cache and self.cache.enabled:
            self.cache.cache_result('deploy', cache_input, result.data.dict(), confidence)

        return result.data

    def decide_strategy_sync(
        self,
        image_tag: str,
        test_status: str,
        environment: str,
        metrics: str,
        files_changed: int = 0,
        session_id: str = None
    ) -> DeployDecision:
        """Synchronous version of decide_strategy for compatibility"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.decide_strategy(image_tag, test_status, environment, metrics, files_changed, session_id)
        )


if __name__ == '__main__':
    """Test DeployAgent with sample data"""

    print("=== DeployAgent Test ===\n")

    # Sample data - successful tests, healthy system
    print("Scenario 1: Healthy System, All Tests Passed")
    agent = DeployAgent()
    decision = agent.decide_strategy_sync(
        image_tag='billionmail:abc123',
        test_status='✓|total:57|passed:57|time:43s',
        environment='production',
        metrics='cpu:45%,mem:60%,disk:70%',
        files_changed=8
    )

    print("Deployment Decision:")
    print(f"  Should Deploy: {decision.should_deploy}")
    print(f"  Reason: {decision.reason}")
    print(f"  Strategy: {decision.strategy}")
    print(f"  Rollback Enabled: {decision.rollback_enabled}")
    print(f"  Health Check Duration: {decision.health_check_duration}s")
    print(f"  Traffic Shift: {decision.traffic_shift}")
    print(f"  Risk Level: {decision.risk_level}")
    if decision.canary_percentage:
        print(f"  Canary Percentage: {decision.canary_percentage}%")
    print()

    # Encode deployment strategy with sns-core
    sns = CICDNotation()
    config = {
        'rollback': 'auto' if decision.rollback_enabled else 'manual',
        'monitor': f'{decision.health_check_duration}s',
        'health': '✓' if decision.should_deploy else '✗'
    }
    encoded = sns.encode_deployment_strategy(decision.strategy, config)
    print(f"SNS-core encoded deployment:\n  {encoded}")
