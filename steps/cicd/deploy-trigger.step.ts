/**
 * Deploy Trigger Step
 *
 * Listens for deployment requests and triggers DeployAgent for strategy decision
 */

import { EventConfig, Handlers } from '../../types';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const config: EventConfig = {
  type: 'event',
  name: 'DeployTrigger',
  description: 'Analyze deployment readiness and determine strategy',
  event: 'cicd.deploy.requested',
};

export const handler: Handlers['DeployTrigger'] = async (event, { emitter, logger }) => {
  try {
    const deployData = event.data;
    const environment = deployData.environment || 'staging'; // Default to staging

    logger.info('Deploy trigger activated', {
      repo: deployData.repo,
      imageTag: deployData.imageTag,
      environment,
    });

    // Get current system metrics (simplified for now)
    const metrics = 'cpu:45%,mem:60%,disk:70%';

    // Encode test results in sns-core notation
    const testStatus = deployData.testResults
      ? `✓|total:${deployData.testResults.totalTests}|passed:${deployData.testResults.passedTests}|time:${deployData.testResults.testTime}s`
      : '✓|total:0|passed:0|time:0s';

    // Call DeployAgent via Python
    const venvPython = '/opt/motia/venv/bin/python';

    // Prepare deployment decision input
    const deployInput = JSON.stringify({
      image_tag: deployData.imageTag,
      test_status: testStatus,
      environment,
      metrics,
      files_changed: deployData.filesChanged || 5, // Default value
    });

    // Execute DeployAgent
    logger.info('Calling DeployAgent for strategy decision', {
      imageTag: deployData.imageTag,
      environment,
    });

    const { stdout } = await execAsync(
      `${venvPython} -c "import sys; sys.path.insert(0, '/opt/motia/agents/cicd/deploy'); from agent import DeployAgent; import json; agent = DeployAgent(); data = json.loads('${deployInput.replace(/'/g, "\\'")}'); result = agent.decide_strategy_sync(data['image_tag'], data['test_status'], data['environment'], data['metrics'], data['files_changed']); print(json.dumps(result.dict()))"`,
      { timeout: 60000 }
    );

    // Parse DeployAgent result
    const deployDecision = JSON.parse(stdout.trim());

    logger.info('DeployAgent decision received', {
      shouldDeploy: deployDecision.should_deploy,
      strategy: deployDecision.strategy,
      riskLevel: deployDecision.risk_level,
    });

    if (!deployDecision.should_deploy) {
      logger.warn('Deployment blocked by AI analysis', {
        reason: deployDecision.reason,
        riskLevel: deployDecision.risk_level,
        repo: deployData.repo,
      });

      // Emit deployment blocked event
      await emitter.emit('cicd.deploy.blocked', {
        repo: deployData.repo,
        commit: deployData.commit,
        environment,
        reason: deployDecision.reason,
        riskLevel: deployDecision.risk_level,
      });

      return;
    }

    // Emit deployment started event
    await emitter.emit('cicd.deploy.started', {
      repo: deployData.repo,
      commit: deployData.commit,
      imageTag: deployData.imageTag,
      environment,
      strategy: deployDecision.strategy,
      riskLevel: deployDecision.risk_level,
      rollbackEnabled: deployDecision.rollback_enabled,
    });

    // Execute deployment based on strategy
    logger.info('Starting deployment', {
      imageTag: deployData.imageTag,
      environment,
      strategy: deployDecision.strategy,
    });

    try {
      const deployStartTime = Date.now();

      // Execute deployment
      // For now, simulate deployment
      // TODO: Implement actual deployment logic (blue-green, canary, etc.)

      if (deployDecision.strategy === 'blue-green') {
        logger.info('Executing blue-green deployment', { imageTag: deployData.imageTag });
        // 1. Deploy new version alongside old
        // 2. Run health checks
        // 3. Switch traffic
        // 4. Keep old version for rollback
      } else if (deployDecision.strategy === 'canary') {
        logger.info('Executing canary deployment', {
          imageTag: deployData.imageTag,
          percentage: deployDecision.canary_percentage,
        });
        // 1. Deploy canary with X% traffic
        // 2. Monitor metrics
        // 3. Gradually increase traffic
        // 4. Full rollout or rollback
      } else {
        logger.info('Executing immediate deployment', { imageTag: deployData.imageTag });
        // Direct deployment (dev/staging only)
      }

      const deployTime = Math.floor((Date.now() - deployStartTime) / 1000);

      logger.info('Deployment completed', {
        imageTag: deployData.imageTag,
        environment,
        deployTime: `${deployTime}s`,
      });

      // Emit deployment completed event
      await emitter.emit('cicd.deploy.completed', {
        repo: deployData.repo,
        commit: deployData.commit,
        imageTag: deployData.imageTag,
        environment,
        strategy: deployDecision.strategy,
        deployTime,
        rollbackEnabled: deployDecision.rollback_enabled,
      });

      // Trigger post-deployment monitoring
      await emitter.emit('cicd.monitor.start', {
        repo: deployData.repo,
        commit: deployData.commit,
        imageTag: deployData.imageTag,
        environment,
        deployTime: 0, // Just deployed
        healthCheckDuration: deployDecision.health_check_duration,
      });

    } catch (deployError: any) {
      logger.error('Deployment failed', {
        error: deployError.message,
        imageTag: deployData.imageTag,
        environment,
      });

      // Emit deployment failed event
      await emitter.emit('cicd.deploy.failed', {
        repo: deployData.repo,
        commit: deployData.commit,
        environment,
        error: deployError.message,
      });

      // If rollback is enabled, trigger automatic rollback
      if (deployDecision.rollback_enabled) {
        logger.info('Triggering automatic rollback', {
          repo: deployData.repo,
          environment,
        });

        await emitter.emit('cicd.rollback.triggered', {
          repo: deployData.repo,
          commit: deployData.commit,
          environment,
          reason: 'deployment_failed',
        });
      }
    }

  } catch (error: any) {
    logger.error('Error in deploy trigger', { error: error.message });
  }
};
