"""
sns-core integration for CI/CD workflows
Implements efficient notation system for AI-to-AI communication with 60-85% token reduction
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass


class SNSNotation:
    """Base SNS notation system for compact communication"""

    @staticmethod
    def encode_dict(data: Dict[str, Any]) -> str:
        """
        Encode dictionary to compact notation
        Example: {"repo": "billionmail", "commit": "abc123"} → repo:billionmail|commit:abc123
        """
        return '|'.join(f"{k}:{v}" for k, v in data.items())

    @staticmethod
    def decode_dict(notation: str) -> Dict[str, str]:
        """
        Decode compact notation to dictionary
        Example: repo:billionmail|commit:abc123 → {"repo": "billionmail", "commit": "abc123"}
        """
        if not notation:
            return {}
        parts = notation.split('|')
        return {p.split(':')[0]: p.split(':')[1] for p in parts if ':' in p}

    @staticmethod
    def encode_list(items: List[str]) -> str:
        """
        Encode list to comma-separated notation
        Example: ["file1.py", "file2.py"] → file1.py,file2.py
        """
        return ','.join(items)

    @staticmethod
    def decode_list(notation: str) -> List[str]:
        """
        Decode comma-separated notation to list
        Example: file1.py,file2.py → ["file1.py", "file2.py"]
        """
        return notation.split(',') if notation else []


class CICDNotation(SNSNotation):
    """Extended sns-core for CI/CD workflows"""

    # Status symbols
    STATUS_SUCCESS = '✓'
    STATUS_FAILURE = '✗'
    STATUS_PENDING = '⏳'
    STATUS_RUNNING = '🔄'
    STATUS_WARNING = '⚠️'

    def encode_commit(self, data: Dict[str, Any]) -> str:
        """
        Encode commit information

        Args:
            data: Dict with keys: repo, commit, branch, files_changed (optional), lines_changed (optional)

        Returns:
            Compact notation: repo:billionmail|commit:abc123|branch:main|files:api.py,models.py|lines:+45,-12
        """
        base = {
            'repo': data.get('repo', ''),
            'commit': data.get('commit', ''),
            'branch': data.get('branch', 'main')
        }

        if 'files_changed' in data:
            base['files'] = self.encode_list(data['files_changed'])

        if 'lines_changed' in data:
            base['lines'] = data['lines_changed']

        return self.encode_dict(base)

    def decode_commit(self, notation: str) -> Dict[str, Any]:
        """
        Decode commit notation

        Args:
            notation: Compact notation string

        Returns:
            Dictionary with commit information
        """
        data = self.decode_dict(notation)

        if 'files' in data:
            data['files_changed'] = self.decode_list(data.pop('files'))

        return data

    def encode_workflow(self, steps: List[str]) -> str:
        """
        Encode workflow steps

        Args:
            steps: List of workflow steps

        Returns:
            Compact notation: build → test → deploy
        """
        return ' → '.join(steps)

    def decode_workflow(self, notation: str) -> List[str]:
        """
        Decode workflow notation

        Args:
            notation: Compact notation string

        Returns:
            List of workflow steps
        """
        return [step.strip() for step in notation.split('→')]

    def encode_result(self, success: bool, details: Optional[Dict[str, Any]] = None) -> str:
        """
        Encode execution result

        Args:
            success: Whether the operation succeeded
            details: Optional dictionary with additional details

        Returns:
            Compact notation: ✓|img:billionmail:abc123|time:120s
        """
        status = self.STATUS_SUCCESS if success else self.STATUS_FAILURE

        if details:
            detail_str = '|'.join(f"{k}:{v}" for k, v in details.items())
            return f"{status}|{detail_str}"

        return status

    def decode_result(self, notation: str) -> Dict[str, Any]:
        """
        Decode result notation

        Args:
            notation: Compact notation string

        Returns:
            Dictionary with success status and details
        """
        parts = notation.split('|')
        success = parts[0] == self.STATUS_SUCCESS

        details = {}
        for part in parts[1:]:
            if ':' in part:
                key, value = part.split(':', 1)
                details[key] = value

        return {
            'success': success,
            'details': details
        }

    def encode_build_strategy(self, strategy: str, options: Optional[Dict[str, str]] = None) -> str:
        """
        Encode build strategy

        Args:
            strategy: Build strategy name (cache, no-cache, multi-stage)
            options: Optional dictionary with additional options

        Returns:
            Compact notation: build[cache,prod,linux/amd64]
        """
        opts = [strategy]
        if options:
            opts.extend(options.values())

        opts_str = ','.join(opts)
        return f"build[{opts_str}]"

    def decode_build_strategy(self, notation: str) -> Dict[str, Any]:
        """
        Decode build strategy notation

        Args:
            notation: Compact notation string

        Returns:
            Dictionary with strategy and options
        """
        # Extract content between brackets
        content = notation[notation.index('[')+1:notation.index(']')]
        opts = content.split(',')

        return {
            'strategy': opts[0] if opts else 'cache',
            'options': opts[1:] if len(opts) > 1 else []
        }

    def encode_test_selection(self, tests_to_run: List[str], tests_to_skip: List[str]) -> str:
        """
        Encode test selection

        Args:
            tests_to_run: List of tests to execute
            tests_to_skip: List of tests to skip

        Returns:
            Compact notation: test[unit:api,unit:models,int:auth] → skip[e2e:ui,perf]
        """
        run_str = self.encode_list(tests_to_run)
        skip_str = self.encode_list(tests_to_skip)

        return f"test[{run_str}] → skip[{skip_str}]"

    def decode_test_selection(self, notation: str) -> Dict[str, List[str]]:
        """
        Decode test selection notation

        Args:
            notation: Compact notation string

        Returns:
            Dictionary with tests_to_run and tests_to_skip
        """
        parts = notation.split(' → ')

        # Extract tests to run
        run_content = parts[0][parts[0].index('[')+1:parts[0].index(']')]
        tests_to_run = self.decode_list(run_content)

        # Extract tests to skip
        tests_to_skip = []
        if len(parts) > 1:
            skip_content = parts[1][parts[1].index('[')+1:parts[1].index(']')]
            tests_to_skip = self.decode_list(skip_content)

        return {
            'tests_to_run': tests_to_run,
            'tests_to_skip': tests_to_skip
        }

    def encode_deployment_strategy(self, strategy: str, config: Dict[str, Any]) -> str:
        """
        Encode deployment strategy

        Args:
            strategy: Deployment strategy name (blue-green, canary, rolling)
            config: Dictionary with deployment configuration

        Returns:
            Compact notation: deploy[blue-green]|rollback[auto]|monitor[5m]
        """
        parts = [f"deploy[{strategy}]"]

        for key, value in config.items():
            parts.append(f"{key}[{value}]")

        return '|'.join(parts)

    def decode_deployment_strategy(self, notation: str) -> Dict[str, Any]:
        """
        Decode deployment strategy notation

        Args:
            notation: Compact notation string

        Returns:
            Dictionary with strategy and configuration
        """
        parts = notation.split('|')

        # Extract strategy from first part
        strategy_part = parts[0]
        strategy = strategy_part[strategy_part.index('[')+1:strategy_part.index(']')]

        # Extract configuration from remaining parts
        config = {}
        for part in parts[1:]:
            key = part[:part.index('[')]
            value = part[part.index('[')+1:part.index(']')]
            config[key] = value

        return {
            'strategy': strategy,
            'config': config
        }


@dataclass
class CICDMessage:
    """Structured message for CI/CD agent communication"""

    source: str  # Agent that sent the message (BuildAgent, TestAgent, etc.)
    target: str  # Agent that should receive the message
    operation: str  # Operation type (analyze_commit, run_tests, deploy, etc.)
    payload: str  # SNS-encoded payload
    session_id: str  # Session identifier for tracking

    def to_dict(self) -> Dict[str, str]:
        """Convert message to dictionary for serialization"""
        return {
            'source': self.source,
            'target': self.target,
            'operation': self.operation,
            'payload': self.payload,
            'session_id': self.session_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'CICDMessage':
        """Create message from dictionary"""
        return cls(
            source=data['source'],
            target=data['target'],
            operation=data['operation'],
            payload=data['payload'],
            session_id=data['session_id']
        )


# Singleton instance
sns = CICDNotation()
