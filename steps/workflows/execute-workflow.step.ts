/**
 * Execute Workflow API Step
 *
 * Main API endpoint for starting and managing workflow executions
 * Provides unified interface for all orchestrated operations
 */

import { ApiRouteConfig, Handlers } from 'motia';
import { z } from 'zod';

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'ExecuteWorkflow',
  description: 'Execute an orchestrated workflow',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/workflows/:workflowId/execute',
  emits: [],

  bodySchema: z.object({
    params: z.record(z.any()).optional().describe('Workflow parameters'),
    metadata: z.object({
      userId: z.string().optional(),
      requestId: z.string().optional(),
      correlationId: z.string().optional(),
    }).optional(),
  }),

  responseSchema: {
    202: z.object({
      workflowId: z.string(),
      executionId: z.string(),
      status: z.string(),
      currentStep: z.string().optional(),
      stateUrl: z.string(),
      createdAt: z.string(),
    }),
    400: z.object({ error: z.string() }),
    404: z.object({ error: z.string() }),
    500: z.object({ error: z.string(), details: z.any().optional() }),
  },
};

export const handler: Handlers['ExecuteWorkflow'] = async (req: any, { logger }: any) => {
  const { workflowId } = req.params;
  const { params = {}, metadata = {} } = req.body;

  try {
    logger.info('Workflow execution request', {
      workflowId,
      paramKeys: Object.keys(params),
      userId: metadata.userId,
    });

    // Validate workflow exists
    const workflow = await req.context.workflowEngine.getWorkflow(workflowId);
    if (!workflow) {
      return {
        status: 404,
        body: { error: `Workflow not found: ${workflowId}` },
      };
    }

    // Generate request ID if not provided
    const requestId = metadata.requestId || `req-${Date.now()}-${Math.random().toString(36).substring(7)}`;
    const correlationId = metadata.correlationId || requestId;

    // Start workflow execution
    const execution = await req.context.workflowEngine.execute(
      workflowId,
      params,
      {
        requestId,
        correlationId,
        userId: metadata.userId,
        triggeredBy: 'api',
      }
    );

    logger.info('Workflow execution started', {
      executionId: execution.id,
      workflowId,
      requestId,
    });

    return {
      status: 202,  // Accepted (async execution)
      body: {
        workflowId,
        executionId: execution.id,
        status: execution.status,
        currentStep: execution.currentStepId,
        stateUrl: `/api/workflows/${workflowId}/${execution.id}`,
        createdAt: execution.startTime.toISOString(),
      },
      headers: {
        'Location': `/api/workflows/${workflowId}/${execution.id}`,
        'Retry-After': '5',
      },
    };

  } catch (error: any) {
    logger.error('Workflow execution failed', {
      workflowId,
      error: error.message,
      stack: error.stack,
    });

    return {
      status: 500,
      body: {
        error: 'Workflow execution failed',
        details: {
          message: error.message,
          workflowId,
        },
      },
    };
  }
};

/**
 * Get Workflow Execution State
 */
export const getStateConfig: ApiRouteConfig = {
  type: 'api',
  name: 'GetWorkflowState',
  description: 'Get current state of a workflow execution',
  flows: ['vps-orchestration'],
  method: 'GET',
  path: '/api/workflows/:workflowId/:executionId',
  emits: [],

  responseSchema: {
    200: z.object({
      executionId: z.string(),
      workflowId: z.string(),
      status: z.enum(['pending', 'running', 'completed', 'failed', 'cancelled']),
      currentStep: z.string().optional(),
      progress: z.object({
        total: z.number(),
        completed: z.number(),
        percentage: z.number(),
      }),
      output: z.record(z.any()).optional(),
      error: z.any().optional(),
      createdAt: z.string(),
      updatedAt: z.string(),
      completedAt: z.string().optional(),
    }),
    404: z.object({ error: z.string() }),
  },
};

export const getStateHandler: Handlers['GetWorkflowState'] = async (req: any, { logger }: any) => {
  const { workflowId, executionId } = req.params;

  try {
    const execution = await req.context.workflowEngine.getExecution(executionId);

    if (!execution) {
      return {
        status: 404,
        body: { error: `Execution not found: ${executionId}` },
      };
    }

    if (execution.definitionId !== workflowId) {
      return {
        status: 404,
        body: { error: 'Workflow ID mismatch' },
      };
    }

    // Calculate progress
    const steps = Array.from(execution.steps.values());
    const completed = steps.filter(s => s.status === 'completed' || s.status === 'skipped').length;
    const total = steps.length;

    return {
      status: 200,
      body: {
        executionId: execution.id,
        workflowId: execution.definitionId,
        status: execution.status,
        currentStep: execution.currentStepId,
        progress: {
          total,
          completed,
          percentage: total > 0 ? Math.round((completed / total) * 100) : 0,
        },
        output: execution.output,
        error: execution.error,
        createdAt: execution.startTime.toISOString(),
        updatedAt: (execution.endTime || new Date()).toISOString(),
        completedAt: execution.endTime?.toISOString(),
      },
      headers: {
        'Cache-Control': execution.status === 'completed' ? 'public, max-age=3600' : 'no-cache',
      },
    };

  } catch (error: any) {
    logger.error('Get workflow state failed', {
      executionId,
      error: error.message,
    });

    return {
      status: 500,
      body: { error: 'Failed to retrieve workflow state' },
    };
  }
};

/**
 * Cancel Workflow Execution
 */
export const cancelConfig: ApiRouteConfig = {
  type: 'api',
  name: 'CancelWorkflow',
  description: 'Cancel a running workflow execution',
  flows: ['vps-orchestration'],
  method: 'DELETE',
  path: '/api/workflows/:workflowId/:executionId',
  emits: [],

  responseSchema: {
    200: z.object({ message: z.string(), executionId: z.string() }),
    404: z.object({ error: z.string() }),
    409: z.object({ error: z.string() }),
  },
};

export const cancelHandler: Handlers['CancelWorkflow'] = async (req: any, { logger }: any) => {
  const { workflowId, executionId } = req.params;

  try {
    const execution = await req.context.workflowEngine.getExecution(executionId);

    if (!execution) {
      return {
        status: 404,
        body: { error: `Execution not found: ${executionId}` },
      };
    }

    if (execution.status === 'completed' || execution.status === 'failed') {
      return {
        status: 409,
        body: { error: `Cannot cancel ${execution.status} execution` },
      };
    }

    await req.context.workflowEngine.cancel(executionId);

    logger.info('Workflow cancelled', { executionId, workflowId });

    return {
      status: 200,
      body: {
        message: 'Workflow execution cancelled',
        executionId,
      },
    };

  } catch (error: any) {
    logger.error('Cancel workflow failed', {
      executionId,
      error: error.message,
    });

    return {
      status: 500,
      body: { error: 'Failed to cancel workflow' },
    };
  }
};
