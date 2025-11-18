"""
TestAgent - Intelligent test selection and execution

Analyzes code changes and determines:
- Which tests to run based on file changes
- Which tests can be safely skipped
- Test execution order and parallelization
- Estimated test execution time
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


class TestDecision(BaseModel):
    """Structured test selection decision from AI analysis"""

    tests_to_run: List[str] = Field(description="List of test paths/patterns to execute")
    tests_to_skip: List[str] = Field(description="List of test paths/patterns to skip")
    reason: str = Field(description="Explanation for test selection")
    estimated_time: int = Field(description="Estimated total test execution time in seconds")
    parallel_groups: Optional[List[List[str]]] = Field(
        default=None,
        description="Groups of tests that can run in parallel"
    )
    priority: str = Field(description="Test priority: low, medium, high, critical")


class TestAgent:
    """
    Intelligent test selection agent using Pydantic AI

    Analyzes code changes to determine which tests need to run and optimizes
    test execution through smart selection and parallelization.
    """

    def __init__(self, model: str = None):
        """
        Initialize TestAgent

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
            output_type=TestDecision,
            system_prompt=self._build_system_prompt()
        )

        # Register tools
        self._register_tools()

        # Log provider stats
        stats = self.ollama_provider.get_stats()
        print(f"[TestAgent] Using {stats['backend']} | Cost: {stats['cost']} | Latency: {stats['latency_target']}")

        # Initialize Redis cache for decision caching
        self.cache = AgentCache()
        if self.cache.enabled:
            print(f"[TestAgent] Cache enabled | Confidence threshold: {self.cache.confidence_threshold}")

    def _build_system_prompt(self) -> str:
        """Construct system prompt for TestAgent"""
        return '''You are an expert test selection analyst specializing in intelligent CI/CD optimization.

Your role is to analyze code changes and determine:
1. Which tests must run based on file changes
2. Which tests can be safely skipped
3. Optimal test execution order and parallelization
4. Estimated test execution time

# Test Selection Guidelines

## Must Run Tests
- **Direct changes**: Tests for modified source files
- **API/interface changes**: All integration tests
- **Database/schema changes**: All database-related tests
- **Configuration changes**: Tests affected by config
- **Dependency updates**: All tests (can't predict impact)

## Safe to Skip
- **Unrelated modules**: Tests for completely separate features
- **Documentation only**: When only .md files changed
- **Frontend/Backend separation**: Backend tests when only frontend changed
- **Unchanged components**: Tests for files with no related changes

## Test Types by Priority

### Critical (Always run)
- unit:core - Core business logic
- integration:api - API contract tests
- integration:database - Database integrity tests
- security:auth - Authentication/authorization tests

### High (Run on related changes)
- unit:{module} - Unit tests for changed modules
- integration:{feature} - Integration tests for changed features
- e2e:critical_paths - Critical user journeys

### Medium (Run periodically or on demand)
- e2e:full_suite - Complete E2E test suite
- performance:api - API performance tests
- load:basic - Basic load testing

### Low (Run on schedule or manual)
- e2e:edge_cases - Edge case scenarios
- performance:extended - Extended performance testing
- compatibility:browsers - Cross-browser testing

## Test Parallelization

Group tests by:
1. **Independent modules**: Can run simultaneously
2. **Shared resources**: Run sequentially if they use same DB/services
3. **Execution time**: Balance groups by duration
4. **Dependencies**: Respect test dependencies

## Time Estimation
- Unit tests: ~0.5-2s per file
- Integration tests: ~2-10s per test
- E2E tests: ~10-60s per test
- Performance tests: ~30-300s per test

# Communication Protocol
Input uses sns-core notation:
img:billionmail:abc123|changes:api/routes.py,models/user.py

Output uses structured TestDecision with sns-core encoding available.
'''

    def _register_tools(self):
        """Register tools for the TestAgent"""

        @self.agent.tool
        async def map_files_to_tests(ctx: RunContext[Dict[str, Any]], files: List[str]) -> Dict[str, List[str]]:
            """Map changed files to their corresponding test files"""
            test_mapping = {}

            for file in files:
                tests = []

                # Extract module name
                if '/' in file:
                    parts = file.split('/')
                    module = parts[-1].split('.')[0]
                else:
                    module = file.split('.')[0]

                # Determine test patterns
                if 'api' in file or 'routes' in file:
                    tests.extend([
                        f'unit:api:{module}',
                        'integration:api',
                        'e2e:api_flows'
                    ])
                elif 'models' in file or 'schema' in file:
                    tests.extend([
                        f'unit:models:{module}',
                        'integration:database',
                        'integration:api'
                    ])
                elif 'auth' in file or 'security' in file:
                    tests.extend([
                        f'unit:auth:{module}',
                        'security:auth',
                        'integration:auth',
                        'e2e:auth_flows'
                    ])
                elif 'config' in file or '.env' in file:
                    tests.extend([
                        'integration:config',
                        'e2e:critical_paths'
                    ])
                elif 'frontend' in file or 'ui' in file or 'components' in file:
                    tests.extend([
                        f'unit:frontend:{module}',
                        'e2e:ui'
                    ])
                else:
                    # Generic mapping
                    tests.append(f'unit:{module}')

                test_mapping[file] = tests

            return test_mapping

        @self.agent.tool
        async def categorize_test_types(ctx: RunContext[Dict[str, Any]], tests: List[str]) -> Dict[str, List[str]]:
            """Categorize tests by type for parallelization"""
            categories = {
                'unit': [],
                'integration': [],
                'e2e': [],
                'security': [],
                'performance': []
            }

            for test in tests:
                if ':' in test:
                    test_type = test.split(':')[0]
                    if test_type in categories:
                        categories[test_type].append(test)
                    else:
                        categories['unit'].append(test)
                else:
                    categories['unit'].append(test)

            return categories

        @self.agent.tool
        async def estimate_test_duration(ctx: RunContext[Dict[str, Any]], tests: List[str]) -> int:
            """Estimate total test execution time"""
            duration = 0

            for test in tests:
                if 'unit:' in test:
                    duration += 1  # 1 second per unit test
                elif 'integration:' in test:
                    duration += 5  # 5 seconds per integration test
                elif 'e2e:' in test:
                    duration += 30  # 30 seconds per E2E test
                elif 'security:' in test:
                    duration += 10  # 10 seconds per security test
                elif 'performance:' in test:
                    duration += 60  # 60 seconds per performance test
                else:
                    duration += 2  # Default 2 seconds

            return duration

    async def select_tests(
        self,
        image_tag: str,
        files_changed: List[str],
        session_id: str = None
    ) -> TestDecision:
        """
        Analyze changes and select tests to run with Redis caching

        Args:
            image_tag: Docker image tag that was built
            files_changed: List of files that changed
            session_id: Session identifier for tracking

        Returns:
            TestDecision with structured test selection
        """
        # Create cache key input
        cache_input = {
            'image_tag': image_tag,
            'files_changed': sorted(files_changed),  # Sort for deterministic caching
        }

        # Try to get cached result
        if self.cache and self.cache.enabled:
            cached = self.cache.get_cached_result('test', cache_input)
            if cached:
                result_data = cached.get('result', cached)
                print(f"[TestAgent] ✨ Using cached test selection (saved ~{self.ollama_provider.get_stats()['latency_target']} latency)")
                return TestDecision(**result_data)

        # Cache miss - run AI analysis
        # Encode input with sns-core
        encoded = f"img:{image_tag}|changes:{self.sns.encode_list(files_changed)}"

        # Prepare context for AI
        context = {
            'image_tag': image_tag,
            'files_changed': files_changed,
            'change_count': len(files_changed)
        }

        # Run AI analysis
        result = await self.agent.run(
            f"Analyze changes and select tests: {encoded}",
            deps=context
        )

        # Calculate confidence for caching
        # High confidence if file patterns match known types
        known_patterns = ['api', 'models', 'auth', 'config', 'frontend', 'ui']
        has_known_patterns = any(
            any(pattern in f.lower() for pattern in known_patterns)
            for f in files_changed
        )
        confidence = 0.95 if has_known_patterns else 0.75

        # Cache the result
        if self.cache and self.cache.enabled:
            self.cache.cache_result('test', cache_input, result.data.dict(), confidence)

        return result.data

    def select_tests_sync(
        self,
        image_tag: str,
        files_changed: List[str],
        session_id: str = None
    ) -> TestDecision:
        """
        Synchronous version of select_tests for compatibility

        Args:
            image_tag: Docker image tag that was built
            files_changed: List of files that changed
            session_id: Session identifier for tracking

        Returns:
            TestDecision with structured test selection
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.select_tests(image_tag, files_changed, session_id))

    async def execute_tests(self, decision: TestDecision, test_command: str = "pytest") -> Dict[str, Any]:
        """
        Execute selected tests

        Args:
            decision: TestDecision from select_tests
            test_command: Base test command (e.g., "pytest", "npm test")

        Returns:
            Test execution results
        """
        import subprocess

        if not decision.tests_to_run:
            return {
                'success': True,
                'message': f'No tests to run: {decision.reason}',
                'results': None
            }

        try:
            start_time = datetime.now()
            results = []

            # Execute tests
            for test in decision.tests_to_run:
                # Convert test notation to actual test path
                test_path = test.replace(':', '/').replace('unit/', 'tests/unit/')

                # Run test
                result = subprocess.run(
                    [test_command, test_path, '-v'],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per test group
                )

                results.append({
                    'test': test,
                    'passed': result.returncode == 0,
                    'output': result.stdout
                })

            execution_time = (datetime.now() - start_time).total_seconds()

            # Count results
            total_tests = len(results)
            passed_tests = sum(1 for r in results if r['passed'])

            # Encode result with sns-core
            sns_result = self.sns.encode_result(
                passed_tests == total_tests,
                {
                    'total': str(total_tests),
                    'passed': str(passed_tests),
                    'time': f'{int(execution_time)}s'
                }
            )

            return {
                'success': passed_tests == total_tests,
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': total_tests - passed_tests,
                'execution_time': execution_time,
                'results': results,
                'sns_result': sns_result
            }

        except Exception as e:
            # Encode failure with sns-core
            sns_result = self.sns.encode_result(False, {
                'error': 'test_execution_failed',
                'reason': str(e)[:100]
            })

            return {
                'success': False,
                'error': str(e),
                'sns_result': sns_result
            }


if __name__ == '__main__':
    """Test TestAgent with sample data"""

    # Sample data
    test_files = [
        'src/api/routes.py',
        'src/models/user.py',
        'src/auth/middleware.py',
        'README.md'
    ]

    print("=== TestAgent Test ===\n")
    print(f"Files changed: {len(test_files)}")
    for file in test_files:
        print(f"  - {file}")
    print()

    # Create and run agent
    agent = TestAgent()
    decision = agent.select_tests_sync('billionmail:abc123', test_files)

    print("Test Selection Decision:")
    print(f"  Tests to Run ({len(decision.tests_to_run)}):")
    for test in decision.tests_to_run:
        print(f"    - {test}")
    print()

    if decision.tests_to_skip:
        print(f"  Tests to Skip ({len(decision.tests_to_skip)}):")
        for test in decision.tests_to_skip:
            print(f"    - {test}")
        print()

    print(f"  Reason: {decision.reason}")
    print(f"  Estimated Time: {decision.estimated_time}s")
    print(f"  Priority: {decision.priority}")
    print()

    # Demonstrate sns-core efficiency
    sns = CICDNotation()
    encoded = sns.encode_test_selection(decision.tests_to_run, decision.tests_to_skip)
    print(f"SNS-core encoded test selection:\n  {encoded}")
