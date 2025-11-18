"""
MonitorAgent - Post-deployment health monitoring and validation

Monitors deployed services and determines:
- Whether deployment was successful
- Service health and stability
- When to trigger rollback
- Performance metrics and alerts
"""

import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from sns_core import CICDNotation, CICDMessage
from hybrid_ollama import get_background_ollama
from redis_cache import AgentCache


class MonitorResult(BaseModel):
    """Structured monitoring result from AI analysis"""

    is_healthy: bool = Field(description="Whether the deployment is healthy")
    reason: str = Field(description="Explanation for health assessment")
    should_rollback: bool = Field(description="Whether automatic rollback should trigger")
    confidence: float = Field(description="Confidence in health assessment (0.0-1.0)")
    metrics_summary: Dict[str, Any] = Field(description="Summary of key metrics")
    recommendations: List[str] = Field(description="Recommendations for next actions")
    alert_level: str = Field(description="Alert level: normal, warning, critical")


class MonitorAgent:
    """
    Intelligent post-deployment monitoring agent using Pydantic AI

    Analyzes service health metrics, error rates, and performance to determine
    if a deployment is successful or if rollback is needed.
    """

    def __init__(self, model: str = None):
        """
        Initialize MonitorAgent

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
            output_type=MonitorResult,
            system_prompt=self._build_system_prompt()
        )

        # Register tools
        self._register_tools()

        # Log provider stats
        stats = self.ollama_provider.get_stats()
        print(f"[MonitorAgent] Using {stats['backend']} | Cost: {stats['cost']} | Latency: {stats['latency_target']}")

        # Initialize Redis cache for decision caching
        self.cache = AgentCache()
        if self.cache.enabled:
            print(f"[MonitorAgent] Cache enabled | Confidence threshold: {self.cache.confidence_threshold}")

    def _build_system_prompt(self) -> str:
        """Construct system prompt for MonitorAgent"""
        return '''You are an expert SRE (Site Reliability Engineer) specializing in post-deployment monitoring and validation.

Your role is to analyze service health metrics and determine:
1. Whether the deployment is successful and healthy
2. If automatic rollback should be triggered
3. Performance and stability assessment
4. Actionable recommendations for operations team

# Health Assessment Guidelines

## Deployment Success Criteria

### HEALTHY (Green) - Normal Operations
- HTTP error rate: <0.1%
- Response time (p95): <200ms
- Response time (p99): <500ms
- CPU usage: <60%
- Memory usage: <70%
- No crash/restart events
- All health checks passing

### WARNING (Yellow) - Monitor Closely
- HTTP error rate: 0.1% - 1%
- Response time (p95): 200-500ms
- Response time (p99): 500-1000ms
- CPU usage: 60-80%
- Memory usage: 70-85%
- Occasional health check failures
- Minor performance degradation

### CRITICAL (Red) - Consider Rollback
- HTTP error rate: >1%
- Response time (p95): >500ms
- Response time (p99): >1000ms
- CPU usage: >80%
- Memory usage: >85%
- Frequent crash/restart events
- Health check failures
- Database connection errors
- External service timeouts

## Rollback Triggers

### IMMEDIATE Rollback If:
- Error rate spike >5% within 5 minutes
- Complete service outage (all health checks fail)
- Critical security vulnerability discovered
- Data corruption detected
- Payment processing failures

### CONSIDER Rollback If:
- Error rate sustained >2% for 10 minutes
- Response time degradation >50%
- Memory leaks detected (growing memory usage)
- Cascading failures to dependent services
- User-reported critical issues

### MONITOR (No Rollback) If:
- Error rate increase <2%
- Response time within acceptable range
- Resource usage stable
- No critical errors
- Isolated minor issues

## Monitoring Windows

### Initial Monitoring (First 5 minutes)
- Watch for immediate failures
- Monitor startup stability
- Check health endpoints
- Validate basic functionality

### Short-term Monitoring (5-30 minutes)
- Track error rates and response times
- Monitor resource usage trends
- Check for memory leaks
- Validate all endpoints working

### Long-term Monitoring (30-60+ minutes)
- Assess stability under load
- Monitor for slow memory/resource leaks
- Check for edge case failures
- Validate business metrics

## Metrics Interpretation

### Error Rate Trends
- Increasing: Likely deployment issue
- Stable (low): Deployment successful
- Stable (high): Pre-existing issue
- Decreasing: System recovering

### Response Time Trends
- Increasing: Performance regression
- Stable: No performance impact
- Decreasing: Performance improvement
- Spiky: Intermittent issues

### Resource Usage Trends
- Increasing linearly: Memory leak
- Stable: Healthy
- Decreasing: Efficient improvement
- Spiky: Load-dependent issues

## Confidence Scoring

### High Confidence (>0.8)
- Clear metrics trends
- Multiple data points
- Consistent signals across metrics
- Sufficient monitoring time

### Medium Confidence (0.5-0.8)
- Some conflicting signals
- Limited data points
- Partial metric coverage
- Early in monitoring window

### Low Confidence (<0.5)
- Conflicting signals
- Insufficient data
- Very early monitoring
- Missing key metrics

# Communication Protocol
Input uses sns-core notation:
deploy:success|service:billionmail|time:5m|error_rate:0.05%|response_p95:150ms

Output provides structured MonitorResult.
'''

    def _register_tools(self):
        """Register tools for the MonitorAgent"""

        @self.agent.tool
        async def parse_deployment_metrics(ctx: RunContext[Dict[str, Any]], metrics: str) -> Dict[str, Any]:
            """Parse deployment metrics from sns-core notation"""
            metric_dict = {}

            for metric in metrics.split('|'):
                if ':' in metric:
                    key, value = metric.split(':', 1)
                    metric_dict[key] = value

            return metric_dict

        @self.agent.tool
        async def assess_error_rate(ctx: RunContext[Dict[str, Any]], error_rate: str) -> Dict[str, Any]:
            """Assess error rate health"""
            # Remove % and convert to float
            rate = float(error_rate.replace('%', ''))

            if rate < 0.1:
                status = 'healthy'
                severity = 'normal'
            elif rate < 1.0:
                status = 'warning'
                severity = 'warning'
            elif rate < 5.0:
                status = 'degraded'
                severity = 'critical'
            else:
                status = 'failing'
                severity = 'critical'

            return {
                'rate': rate,
                'status': status,
                'severity': severity,
                'should_rollback': rate >= 2.0
            }

        @self.agent.tool
        async def assess_response_time(ctx: RunContext[Dict[str, Any]], p95: str, p99: str) -> Dict[str, Any]:
            """Assess response time health"""
            # Remove 'ms' and convert to int
            p95_val = int(p95.replace('ms', ''))
            p99_val = int(p99.replace('ms', ''))

            if p95_val < 200 and p99_val < 500:
                status = 'healthy'
                severity = 'normal'
            elif p95_val < 500 and p99_val < 1000:
                status = 'warning'
                severity = 'warning'
            else:
                status = 'degraded'
                severity = 'critical'

            return {
                'p95': p95_val,
                'p99': p99_val,
                'status': status,
                'severity': severity
            }

        @self.agent.tool
        async def assess_resource_usage(ctx: RunContext[Dict[str, Any]], cpu: str, memory: str) -> Dict[str, Any]:
            """Assess resource usage health"""
            cpu_val = float(cpu.replace('%', ''))
            mem_val = float(memory.replace('%', ''))

            if cpu_val < 60 and mem_val < 70:
                status = 'healthy'
                severity = 'normal'
            elif cpu_val < 80 and mem_val < 85:
                status = 'moderate'
                severity = 'warning'
            else:
                status = 'high'
                severity = 'critical'

            return {
                'cpu': cpu_val,
                'memory': mem_val,
                'status': status,
                'severity': severity
            }

        @self.agent.tool
        async def calculate_overall_health(
            ctx: RunContext[Dict[str, Any]],
            error_severity: str,
            response_severity: str,
            resource_severity: str
        ) -> Dict[str, Any]:
            """Calculate overall deployment health"""
            severities = [error_severity, response_severity, resource_severity]

            # Count critical and warning signals
            critical_count = severities.count('critical')
            warning_count = severities.count('warning')

            if critical_count >= 2:
                health = 'unhealthy'
                confidence = 0.9
                rollback = True
            elif critical_count == 1:
                health = 'degraded'
                confidence = 0.7
                rollback = error_severity == 'critical'  # Only rollback on error rate issues
            elif warning_count >= 2:
                health = 'warning'
                confidence = 0.6
                rollback = False
            else:
                health = 'healthy'
                confidence = 0.8
                rollback = False

            return {
                'health': health,
                'confidence': confidence,
                'should_rollback': rollback,
                'critical_count': critical_count,
                'warning_count': warning_count
            }

    async def validate_deployment(
        self,
        service_name: str,
        deployment_time: int,
        metrics: str,
        session_id: str = None
    ) -> MonitorResult:
        """
        Validate deployment health based on metrics with Redis caching

        Args:
            service_name: Name of deployed service
            deployment_time: Time since deployment in minutes
            metrics: Service metrics in sns-core notation
                Format: error_rate:0.05%|response_p95:150ms|response_p99:350ms|cpu:45%|memory:60%
            session_id: Session identifier for tracking

        Returns:
            MonitorResult with health assessment
        """
        # Create cache key input
        cache_input = {
            'service_name': service_name,
            'deployment_time': deployment_time,
            'metrics': metrics
        }

        # Try to get cached result
        if self.cache and self.cache.enabled:
            cached = self.cache.get_cached_result('monitor', cache_input)
            if cached:
                result_data = cached.get('result', cached)
                print(f"[MonitorAgent] ✨ Using cached health validation (saved ~{self.ollama_provider.get_stats()['latency_target']} latency)")
                return MonitorResult(**result_data)

        # Cache miss - run AI analysis
        # Encode input with sns-core
        encoded = f"deploy:success|service:{service_name}|time:{deployment_time}m|{metrics}"

        # Prepare context for AI
        context = {
            'service_name': service_name,
            'deployment_time': deployment_time,
            'metrics': metrics
        }

        # Run AI analysis
        result = await self.agent.run(
            f"Validate deployment health: {encoded}",
            deps=context
        )

        # Calculate confidence for caching
        # High confidence for clear healthy/unhealthy states
        if result.data.alert_level in ['normal', 'critical']:
            confidence = 0.95
        elif result.data.alert_level == 'warning':
            confidence = 0.75  # Lower confidence for warning states
        else:
            confidence = 0.85

        # Use the confidence from the result if available
        if hasattr(result.data, 'confidence'):
            confidence = result.data.confidence

        # Cache the result
        if self.cache and self.cache.enabled:
            self.cache.cache_result('monitor', cache_input, result.data.dict(), confidence)

        return result.data

    def validate_deployment_sync(
        self,
        service_name: str,
        deployment_time: int,
        metrics: str,
        session_id: str = None
    ) -> MonitorResult:
        """Synchronous version of validate_deployment for compatibility"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.validate_deployment(service_name, deployment_time, metrics, session_id)
        )


if __name__ == '__main__':
    """Test MonitorAgent with sample data"""

    print("=== MonitorAgent Test ===\n")

    # Scenario 1: Healthy deployment
    print("Scenario 1: Healthy Deployment After 10 Minutes")
    agent = MonitorAgent()
    result = agent.validate_deployment_sync(
        service_name='billionmail',
        deployment_time=10,
        metrics='error_rate:0.05%|response_p95:150ms|response_p99:350ms|cpu:45%|memory:60%'
    )

    print("Monitor Result:")
    print(f"  Is Healthy: {result.is_healthy}")
    print(f"  Reason: {result.reason}")
    print(f"  Should Rollback: {result.should_rollback}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Alert Level: {result.alert_level}")
    print(f"  Metrics Summary: {result.metrics_summary}")
    print("  Recommendations:")
    for rec in result.recommendations:
        print(f"    - {rec}")
    print()

    # Scenario 2: Degraded deployment
    print("Scenario 2: Degraded Deployment - High Error Rate")
    result2 = agent.validate_deployment_sync(
        service_name='billionmail',
        deployment_time=5,
        metrics='error_rate:2.5%|response_p95:450ms|response_p99:900ms|cpu:75%|memory:80%'
    )

    print("Monitor Result:")
    print(f"  Is Healthy: {result2.is_healthy}")
    print(f"  Reason: {result2.reason}")
    print(f"  Should Rollback: {result2.should_rollback}")
    print(f"  Confidence: {result2.confidence}")
    print(f"  Alert Level: {result2.alert_level}")
