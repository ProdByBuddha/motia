/**
 * Register Workflows Endpoint
 *
 * Provides an API endpoint to register workflows into the workflow engine
 * This can be called on startup or on-demand to initialize the system
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'RegisterWorkflows',
  description: 'Register built-in workflows into the engine',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/system/register-workflows',
  emits: [],

  bodySchema: z.object({
    force: z.boolean().optional().describe('Force re-registration even if already registered'),
  }),

  responseSchema: {
    200: z.object({
      message: z.string(),
      workflowsRegistered: z.array(z.object({
        id: z.string(),
        name: z.string(),
        version: z.string(),
        steps: z.number(),
      })),
      timestamp: z.string(),
    }),
    500: z.object({ error: z.string(), details: z.any().optional() }),
  },
};

export const handler = async (input: any, context: any) => {
  const { logger, workflowEngine } = context;
  const { force = false } = input || {};

  try {
    logger.info('Workflow registration requested', { force });

    // Dynamically import the workflow definition
    const { ResearchAnalysisSummaryWorkflow } = await import('../../workflows/examples/research-analysis-summary.workflow');

    const workflows = [ResearchAnalysisSummaryWorkflow];
    const registered = [];

    for (const workflow of workflows) {
      try {
        await workflowEngine.registerWorkflow(workflow);
        logger.info('Workflow registered successfully', {
          workflowId: workflow.id,
          name: workflow.name,
          steps: workflow.steps?.length || 0,
        });

        registered.push({
          id: workflow.id,
          name: workflow.name,
          version: workflow.version || '1.0.0',
          steps: workflow.steps?.length || 0,
        });
      } catch (error: any) {
        logger.warn('Workflow registration warning', {
          workflowId: workflow.id,
          reason: error.message,
        });
        // Continue registering other workflows even if one fails
      }
    }

    return {
      status: 200,
      body: {
        message: `Successfully registered ${registered.length} workflow(s)`,
        workflowsRegistered: registered,
        timestamp: new Date().toISOString(),
      },
    };
  } catch (error: any) {
    logger.error('Workflow registration failed', {
      error: error.message,
      stack: error.stack,
    });

    return {
      status: 500,
      body: {
        error: 'Failed to register workflows',
        details: { message: error.message },
      },
    };
  }
};
