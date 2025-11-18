/**
 * GitHub Webhook Handler for CI/CD Pipeline
 *
 * Receives GitHub push/commit webhooks and triggers the CI/CD workflow
 */

import { z } from 'zod';
import { ApiRouteConfig, Handlers } from '../../types';

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'GitHubWebhook',
  description: 'Receive GitHub webhook events and trigger CI/CD pipeline',
  method: 'POST',
  path: '/api/cicd/webhook/github',
  bodySchema: z.object({
    ref: z.string().optional(),
    repository: z.object({
      name: z.string(),
      full_name: z.string(),
      clone_url: z.string().optional(),
    }).optional(),
    commits: z.array(z.object({
      id: z.string(),
      message: z.string(),
      author: z.object({
        name: z.string(),
        email: z.string().optional(),
      }).optional(),
      added: z.array(z.string()).optional(),
      modified: z.array(z.string()).optional(),
      removed: z.array(z.string()).optional(),
    })).optional(),
    head_commit: z.object({
      id: z.string(),
      message: z.string(),
      added: z.array(z.string()).optional(),
      modified: z.array(z.string()).optional(),
      removed: z.array(z.string()).optional(),
    }).optional(),
  }),
};

export const handler: Handlers['GitHubWebhook'] = async (req, { emitter, logger }) => {
  try {
    const body = req.body;

    // Extract repository name
    const repoName = body.repository?.name || 'unknown';
    const repoFullName = body.repository?.full_name || 'unknown';

    // Extract branch
    const branch = body.ref?.replace('refs/heads/', '') || 'main';

    // Get head commit or last commit
    const commit = body.head_commit || (body.commits && body.commits[body.commits.length - 1]);

    if (!commit) {
      logger.warn('No commit information in webhook', { repoName, branch });
      return {
        status: 400,
        body: { error: 'No commit information provided' }
      };
    }

    // Collect all changed files
    const filesChanged = [
      ...(commit.added || []),
      ...(commit.modified || []),
      ...(commit.removed || [])
    ];

    // Calculate line changes (approximate from number of files)
    const linesChanged = `+${filesChanged.length * 10},-${filesChanged.length * 2}`;

    // Prepare commit data for CI/CD pipeline
    const commitData = {
      repo: repoName,
      repoFullName,
      commit: commit.id.substring(0, 7), // Short hash
      commitFull: commit.id,
      branch,
      message: commit.message,
      author: commit.author?.name || 'unknown',
      filesChanged,
      linesChanged,
      timestamp: new Date().toISOString(),
    };

    logger.info('GitHub webhook received', {
      repo: repoName,
      commit: commitData.commit,
      branch,
      filesCount: filesChanged.length,
    });

    // Emit event to trigger CI/CD pipeline
    await emitter.emit('cicd.commit.received', commitData);

    return {
      status: 202,
      body: {
        message: 'Webhook received, CI/CD pipeline triggered',
        commit: commitData.commit,
        repo: repoName,
        branch,
      }
    };

  } catch (error) {
    logger.error('Error processing GitHub webhook', { error });
    return {
      status: 500,
      body: { error: 'Internal server error processing webhook' }
    };
  }
};
