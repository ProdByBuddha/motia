"""
Test suite for sns-core CI/CD notation system
"""

from sns_core import CICDNotation, CICDMessage


def test_commit_encoding():
    """Test commit data encoding and decoding"""
    sns = CICDNotation()

    commit_data = {
        'repo': 'billionmail',
        'commit': 'abc123def456',
        'branch': 'main',
        'files_changed': ['api/routes.py', 'models/user.py'],
        'lines_changed': '+45,-12'
    }

    encoded = sns.encode_commit(commit_data)
    print(f"✓ Commit encoded: {encoded}")

    decoded = sns.decode_commit(encoded)
    print(f"✓ Commit decoded: {decoded}")

    assert decoded['repo'] == 'billionmail'
    assert decoded['commit'] == 'abc123def456'
    assert len(decoded['files_changed']) == 2


def test_workflow_encoding():
    """Test workflow steps encoding"""
    sns = CICDNotation()

    steps = ['build', 'test', 'deploy']
    encoded = sns.encode_workflow(steps)
    print(f"✓ Workflow encoded: {encoded}")

    decoded = sns.decode_workflow(encoded)
    print(f"✓ Workflow decoded: {decoded}")

    assert decoded == steps


def test_result_encoding():
    """Test result encoding with details"""
    sns = CICDNotation()

    # Success case
    result = sns.encode_result(True, {'img': 'billionmail:abc123', 'time': '120s'})
    print(f"✓ Result encoded: {result}")

    decoded = sns.decode_result(result)
    print(f"✓ Result decoded: {decoded}")

    assert decoded['success'] is True
    assert decoded['details']['img'] == 'billionmail:abc123'

    # Failure case
    result = sns.encode_result(False, {'error': 'build_failed', 'reason': 'dockerfile_error'})
    print(f"✓ Failure encoded: {result}")


def test_build_strategy_encoding():
    """Test build strategy encoding"""
    sns = CICDNotation()

    encoded = sns.encode_build_strategy('cache', {'target': 'prod', 'platform': 'linux/amd64'})
    print(f"✓ Build strategy encoded: {encoded}")

    decoded = sns.decode_build_strategy(encoded)
    print(f"✓ Build strategy decoded: {decoded}")

    assert decoded['strategy'] == 'cache'


def test_test_selection_encoding():
    """Test test selection encoding"""
    sns = CICDNotation()

    tests_to_run = ['unit:api', 'unit:models', 'integration:auth']
    tests_to_skip = ['e2e:ui', 'performance']

    encoded = sns.encode_test_selection(tests_to_run, tests_to_skip)
    print(f"✓ Test selection encoded: {encoded}")

    decoded = sns.decode_test_selection(encoded)
    print(f"✓ Test selection decoded: {decoded}")

    assert len(decoded['tests_to_run']) == 3
    assert len(decoded['tests_to_skip']) == 2


def test_deployment_strategy_encoding():
    """Test deployment strategy encoding"""
    sns = CICDNotation()

    encoded = sns.encode_deployment_strategy('blue-green', {
        'rollback': 'auto',
        'monitor': '5m',
        'health': '✓'
    })
    print(f"✓ Deployment strategy encoded: {encoded}")

    decoded = sns.decode_deployment_strategy(encoded)
    print(f"✓ Deployment strategy decoded: {decoded}")

    assert decoded['strategy'] == 'blue-green'
    assert decoded['config']['rollback'] == 'auto'


def test_cicd_message():
    """Test CICD message structure"""
    msg = CICDMessage(
        source='BuildAgent',
        target='TestAgent',
        operation='build_complete',
        payload='✓|img:billionmail:abc123|time:120s',
        session_id='session_12345'
    )

    msg_dict = msg.to_dict()
    print(f"✓ Message to dict: {msg_dict}")

    msg_restored = CICDMessage.from_dict(msg_dict)
    print(f"✓ Message restored: {msg_restored}")

    assert msg_restored.source == 'BuildAgent'
    assert msg_restored.target == 'TestAgent'


def test_token_efficiency():
    """Demonstrate token reduction"""
    sns = CICDNotation()

    # Traditional JSON approach
    traditional = '''
    {
        "repository": "billionmail",
        "commit_hash": "abc123def456",
        "branch": "main",
        "files_changed": ["api/routes.py", "models/user.py"],
        "lines_changed": "+45,-12",
        "build_result": {
            "success": true,
            "image": "billionmail:abc123",
            "build_time": "120s"
        }
    }
    '''

    # SNS-core approach
    commit = sns.encode_commit({
        'repo': 'billionmail',
        'commit': 'abc123def456',
        'branch': 'main',
        'files_changed': ['api/routes.py', 'models/user.py'],
        'lines_changed': '+45,-12'
    })
    result = sns.encode_result(True, {'img': 'billionmail:abc123', 'time': '120s'})
    sns_notation = f"{commit}|{result}"

    print("\n=== Token Efficiency ===")
    print(f"Traditional JSON: {len(traditional)} characters")
    print(f"SNS-core notation: {len(sns_notation)} characters")
    print(f"Reduction: {((len(traditional) - len(sns_notation)) / len(traditional) * 100):.1f}%")
    print(f"\nSNS-core: {sns_notation}")


if __name__ == '__main__':
    print("=== Testing sns-core CI/CD Notation System ===\n")

    test_commit_encoding()
    print()

    test_workflow_encoding()
    print()

    test_result_encoding()
    print()

    test_build_strategy_encoding()
    print()

    test_test_selection_encoding()
    print()

    test_deployment_strategy_encoding()
    print()

    test_cicd_message()
    print()

    test_token_efficiency()
    print()

    print("\n✅ All tests passed!")
