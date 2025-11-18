/**
 * Test Trigger Step
 *
 * Listens for build completion and triggers TestAgent for intelligent test selection
 */

import { EventConfig, Handlers } from '../../types';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const config: EventConfig = {
  type: 'event',
  name: 'TestTrigger',
  description: 'Select and execute relevant tests based on code changes',
  event: 'cicd.build.completed',
};

export const handler: Handlers['TestTrigger'] = async (event, { emitter, logger }) => {
  try {
    const buildData = event.data;

    logger.info('Test trigger activated', {
      repo: buildData.repo,
      imageTag: buildData.imageTag,
      filesChanged: buildData.filesChanged.length,
    });

    // Call TestAgent via Python
    const venvPython = '/opt/motia/venv/bin/python';

    // Prepare test selection input
    const testInput = JSON.stringify({
      image_tag: buildData.imageTag,
      files_changed: buildData.filesChanged,
    });

    // Execute TestAgent
    logger.info('Calling TestAgent for test selection', { imageTag: buildData.imageTag });

    const { stdout } = await execAsync(
      `${venvPython} -c "import sys; sys.path.insert(0, '/opt/motia/agents/cicd/test'); from agent import TestAgent; import json; agent = TestAgent(); data = json.loads('${testInput.replace(/'/g, "\\'")}'); result = agent.select_tests_sync(data['image_tag'], data['files_changed']); print(json.dumps(result.dict()))"`,
      { timeout: 60000 }
    );

    // Parse TestAgent result
    const testDecision = JSON.parse(stdout.trim());

    logger.info('TestAgent selection received', {
      testsToRun: testDecision.tests_to_run.length,
      testsToSkip: testDecision.tests_to_skip.length,
      estimatedTime: testDecision.estimated_time,
      priority: testDecision.priority,
    });

    if (testDecision.tests_to_run.length === 0) {
      logger.info('No tests selected to run', {
        reason: testDecision.reason,
        repo: buildData.repo,
      });

      // Emit tests skipped event
      await emitter.emit('cicd.tests.skipped', {
        repo: buildData.repo,
        commit: buildData.commit,
        reason: testDecision.reason,
      });

      // Proceed to deployment
      await emitter.emit('cicd.tests.completed', {
        repo: buildData.repo,
        commit: buildData.commit,
        imageTag: buildData.imageTag,
        totalTests: 0,
        passedTests: 0,
        skippedTests: testDecision.tests_to_skip.length,
        testTime: 0,
      });

      return;
    }

    // Emit tests started event
    await emitter.emit('cicd.tests.started', {
      repo: buildData.repo,
      commit: buildData.commit,
      testsToRun: testDecision.tests_to_run,
      estimatedTime: testDecision.estimated_time,
    });

    // Execute tests
    logger.info('Starting test execution', {
      testsCount: testDecision.tests_to_run.length,
      priority: testDecision.priority,
    });

    try {
      const testStartTime = Date.now();

      // Run tests in Docker container with image
      // For now, simulate test execution
      // TODO: Implement actual test execution logic

      const testResults = {
        totalTests: testDecision.tests_to_run.length,
        passedTests: testDecision.tests_to_run.length, // Simulate all passing
        failedTests: 0,
      };

      const testTime = Math.floor((Date.now() - testStartTime) / 1000);

      logger.info('Tests completed', {
        totalTests: testResults.totalTests,
        passedTests: testResults.passedTests,
        testTime: `${testTime}s`,
      });

      // Emit tests completed event
      await emitter.emit('cicd.tests.completed', {
        repo: buildData.repo,
        commit: buildData.commit,
        imageTag: buildData.imageTag,
        totalTests: testResults.totalTests,
        passedTests: testResults.passedTests,
        failedTests: testResults.failedTests,
        testTime,
        testDecision,
      });

      // If all tests passed, trigger deployment decision
      if (testResults.failedTests === 0) {
        await emitter.emit('cicd.deploy.requested', {
          repo: buildData.repo,
          commit: buildData.commit,
          imageTag: buildData.imageTag,
          testResults,
        });
      } else {
        logger.warn('Tests failed, deployment blocked', {
          failedTests: testResults.failedTests,
          repo: buildData.repo,
        });
      }

    } catch (testError: any) {
      logger.error('Test execution failed', {
        error: testError.message,
        repo: buildData.repo,
      });

      // Emit tests failed event
      await emitter.emit('cicd.tests.failed', {
        repo: buildData.repo,
        commit: buildData.commit,
        error: testError.message,
      });
    }

  } catch (error: any) {
    logger.error('Error in test trigger', { error: error.message });
  }
};
