/**
 * Build Trigger Step
 *
 * Listens for commit events and triggers BuildAgent to analyze and execute builds
 */

import { EventConfig, Handlers } from '../../types';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const config: EventConfig = {
  type: 'event',
  name: 'BuildTrigger',
  description: 'Analyze commits and trigger intelligent builds',
  event: 'cicd.commit.received',
};

export const handler: Handlers['BuildTrigger'] = async (event, { emitter, logger }) => {
  try {
    const commitData = event.data;

    logger.info('Build trigger activated', {
      repo: commitData.repo,
      commit: commitData.commit,
      filesChanged: commitData.filesChanged.length,
    });

    // Call BuildAgent via Python
    const agentPath = '/opt/motia/agents/cicd/build/agent.py';
    const venvPython = '/opt/motia/venv/bin/python';

    // Prepare commit data as JSON
    const commitJson = JSON.stringify({
      repo: commitData.repo,
      commit: commitData.commit,
      branch: commitData.branch,
      files_changed: commitData.filesChanged,
      lines_changed: commitData.linesChanged,
    });

    // Execute BuildAgent
    logger.info('Calling BuildAgent for analysis', { repo: commitData.repo });

    const { stdout, stderr } = await execAsync(
      `${venvPython} -c "import sys; sys.path.insert(0, '${agentPath.replace('/agent.py', '')}'); from agent import BuildAgent; import json; agent = BuildAgent(); data = json.loads('${commitJson.replace(/'/g, "\\'")}'); result = agent.analyze_commit_sync(data); print(json.dumps(result.dict()))"`,
      { timeout: 60000 } // 60 second timeout
    );

    // Parse BuildAgent result
    const buildDecision = JSON.parse(stdout.trim());

    logger.info('BuildAgent decision received', {
      shouldBuild: buildDecision.should_build,
      strategy: buildDecision.strategy,
      priority: buildDecision.priority,
    });

    if (!buildDecision.should_build) {
      logger.info('Build skipped based on AI analysis', {
        reason: buildDecision.reason,
        repo: commitData.repo,
      });

      // Emit build skipped event
      await emitter.emit('cicd.build.skipped', {
        repo: commitData.repo,
        commit: commitData.commit,
        reason: buildDecision.reason,
      });

      return;
    }

    // Emit build started event
    await emitter.emit('cicd.build.started', {
      repo: commitData.repo,
      commit: commitData.commit,
      strategy: buildDecision.strategy,
      estimatedTime: buildDecision.estimated_time,
      priority: buildDecision.priority,
    });

    // Execute Docker build
    const imageTag = `${commitData.repo}:${commitData.commit}`;

    logger.info('Starting Docker build', {
      imageTag,
      strategy: buildDecision.strategy,
    });

    try {
      // Build Docker image
      const buildCmd = buildDecision.strategy === 'no-cache'
        ? `docker build --no-cache -t ${imageTag} .`
        : `docker build -t ${imageTag} .`;

      const buildStartTime = Date.now();
      const { stdout: buildOutput } = await execAsync(
        buildCmd,
        {
          cwd: `/path/to/${commitData.repo}`, // TODO: Configure repository paths
          timeout: 600000 // 10 minute timeout
        }
      );
      const buildTime = Math.floor((Date.now() - buildStartTime) / 1000);

      logger.info('Docker build completed', {
        imageTag,
        buildTime: `${buildTime}s`,
      });

      // Emit build completed event
      await emitter.emit('cicd.build.completed', {
        repo: commitData.repo,
        commit: commitData.commit,
        imageTag,
        buildTime,
        strategy: buildDecision.strategy,
        filesChanged: commitData.filesChanged,
      });

    } catch (buildError: any) {
      logger.error('Docker build failed', {
        error: buildError.message,
        imageTag,
      });

      // Emit build failed event
      await emitter.emit('cicd.build.failed', {
        repo: commitData.repo,
        commit: commitData.commit,
        error: buildError.message,
      });
    }

  } catch (error: any) {
    logger.error('Error in build trigger', { error: error.message });
  }
};
