/**
 * Monitor Trigger Step
 *
 * Monitors deployed services and validates health using MonitorAgent
 */

import { EventConfig, Handlers } from '../../types';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const config: EventConfig = {
  type: 'event',
  name: 'MonitorTrigger',
  description: 'Monitor deployment health and trigger rollback if needed',
  event: 'cicd.monitor.start',
};

export const handler: Handlers['MonitorTrigger'] = async (event, { emitter, logger }) => {
  try {
    const monitorData = event.data;

    logger.info('Monitor trigger activated', {
      repo: monitorData.repo,
      imageTag: monitorData.imageTag,
      environment: monitorData.environment,
    });

    // Calculate monitoring duration
    const healthCheckDuration = monitorData.healthCheckDuration || 300; // Default 5 minutes
    const checkInterval = 30; // Check every 30 seconds
    const maxChecks = Math.ceil(healthCheckDuration / checkInterval);

    let currentCheck = 0;
    let consecutiveHealthyChecks = 0;
    let consecutiveUnhealthyChecks = 0;

    // Emit monitoring started event
    await emitter.emit('cicd.monitor.started', {
      repo: monitorData.repo,
      commit: monitorData.commit,
      environment: monitorData.environment,
      duration: healthCheckDuration,
    });

    // Monitoring loop
    const monitoringInterval = setInterval(async () => {
      try {
        currentCheck++;
        const deploymentTime = Math.floor((currentCheck * checkInterval) / 60); // Minutes since deployment

        // Get current service metrics (simplified for now)
        // TODO: Integrate with actual monitoring system (Prometheus, etc.)
        const metrics = 'error_rate:0.05%|response_p95:150ms|response_p99:350ms|cpu:45%|memory:60%';

        logger.info('Running health check', {
          check: `${currentCheck}/${maxChecks}`,
          deploymentTime: `${deploymentTime}m`,
          repo: monitorData.repo,
        });

        // Call MonitorAgent via Python
        const venvPython = '/opt/motia/venv/bin/python';

        // Prepare monitoring input
        const monitorInput = JSON.stringify({
          service_name: monitorData.repo,
          deployment_time: deploymentTime,
          metrics,
        });

        // Execute MonitorAgent
        const { stdout } = await execAsync(
          `${venvPython} -c "import sys; sys.path.insert(0, '/opt/motia/agents/cicd/monitor'); from agent import MonitorAgent; import json; agent = MonitorAgent(); data = json.loads('${monitorInput.replace(/'/g, "\\'")}'); result = agent.validate_deployment_sync(data['service_name'], data['deployment_time'], data['metrics']); print(json.dumps(result.dict()))"`,
          { timeout: 60000 }
        );

        // Parse MonitorAgent result
        const monitorResult = JSON.parse(stdout.trim());

        logger.info('MonitorAgent validation received', {
          isHealthy: monitorResult.is_healthy,
          shouldRollback: monitorResult.should_rollback,
          alertLevel: monitorResult.alert_level,
          confidence: monitorResult.confidence,
        });

        // Track consecutive healthy/unhealthy checks
        if (monitorResult.is_healthy) {
          consecutiveHealthyChecks++;
          consecutiveUnhealthyChecks = 0;
        } else {
          consecutiveHealthyChecks = 0;
          consecutiveUnhealthyChecks++;
        }

        // Emit health check result
        await emitter.emit('cicd.monitor.check', {
          repo: monitorData.repo,
          commit: monitorData.commit,
          environment: monitorData.environment,
          check: currentCheck,
          totalChecks: maxChecks,
          result: monitorResult,
          consecutiveHealthy: consecutiveHealthyChecks,
          consecutiveUnhealthy: consecutiveUnhealthyChecks,
        });

        // Decision logic
        if (monitorResult.should_rollback || consecutiveUnhealthyChecks >= 3) {
          logger.warn('Health check failed, triggering rollback', {
            reason: monitorResult.reason,
            consecutiveUnhealthy: consecutiveUnhealthyChecks,
            repo: monitorData.repo,
          });

          clearInterval(monitoringInterval);

          // Emit monitoring failed and trigger rollback
          await emitter.emit('cicd.monitor.failed', {
            repo: monitorData.repo,
            commit: monitorData.commit,
            environment: monitorData.environment,
            reason: monitorResult.reason,
            alertLevel: monitorResult.alert_level,
          });

          await emitter.emit('cicd.rollback.triggered', {
            repo: monitorData.repo,
            commit: monitorData.commit,
            environment: monitorData.environment,
            reason: 'health_check_failed',
            monitorResult,
          });

          return;
        }

        // Success criteria: 5 consecutive healthy checks or reached max checks with healthy status
        if (consecutiveHealthyChecks >= 5 || (currentCheck >= maxChecks && monitorResult.is_healthy)) {
          logger.info('Deployment validated successfully', {
            repo: monitorData.repo,
            environment: monitorData.environment,
            checks: currentCheck,
          });

          clearInterval(monitoringInterval);

          // Emit monitoring success
          await emitter.emit('cicd.monitor.success', {
            repo: monitorData.repo,
            commit: monitorData.commit,
            environment: monitorData.environment,
            totalChecks: currentCheck,
            finalResult: monitorResult,
          });

          // Emit deployment fully validated
          await emitter.emit('cicd.deploy.validated', {
            repo: monitorData.repo,
            commit: monitorData.commit,
            imageTag: monitorData.imageTag,
            environment: monitorData.environment,
            monitoringDuration: deploymentTime,
          });

          return;
        }

        // Continue monitoring
        if (currentCheck >= maxChecks) {
          logger.info('Maximum monitoring checks reached', {
            repo: monitorData.repo,
            consecutiveHealthy: consecutiveHealthyChecks,
          });

          clearInterval(monitoringInterval);

          if (monitorResult.is_healthy) {
            // Reached max checks with healthy status - consider validated
            await emitter.emit('cicd.monitor.success', {
              repo: monitorData.repo,
              commit: monitorData.commit,
              environment: monitorData.environment,
              totalChecks: currentCheck,
              finalResult: monitorResult,
            });
          } else {
            // Reached max checks but not consistently healthy
            await emitter.emit('cicd.monitor.warning', {
              repo: monitorData.repo,
              commit: monitorData.commit,
              environment: monitorData.environment,
              totalChecks: currentCheck,
              finalResult: monitorResult,
              message: 'Monitoring completed but health not fully validated',
            });
          }
        }

      } catch (checkError: any) {
        logger.error('Error during health check', {
          error: checkError.message,
          check: currentCheck,
        });
      }

    }, checkInterval * 1000); // Convert to milliseconds

  } catch (error: any) {
    logger.error('Error in monitor trigger', { error: error.message });
  }
};
