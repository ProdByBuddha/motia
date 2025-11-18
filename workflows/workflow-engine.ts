/**
 * Workflow Engine
 *
 * Core orchestration engine for executing multi-step agent workflows
 * Handles state management, step coordination, and error recovery
 */

import { Logger } from 'motia';
import { v4 as uuidv4 } from 'uuid';

interface WorkflowDefinition {
  id: string;
  name: string;
  version: string;
  description: string;

  steps: WorkflowStep[];
  outputs: Record<string, string>;  // Template references

  metadata?: {
    owner?: string;
    tags?: string[];
  };
}

interface WorkflowStep {
  id: string;
  agentId: string;

  input: Record<string, any>;
  condition?: string;

  onError?: 'fail' | 'continue' | 'retry' | 'alternate';
  alternateStepId?: string;

  timeout?: number;
  retryPolicy?: {
    maxAttempts: number;
    backoffMs: number;
    exponential?: boolean;
  };

  outputPath?: string;
}

interface WorkflowExecutionState {
  id: string;
  definitionId: string;

  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  startTime: Date;
  endTime?: Date;

  input: Record<string, any>;
  output?: Record<string, any>;
  error?: {
    stepId: string;
    code: string;
    message: string;
  };

  steps: Map<string, StepExecutionState>;
  currentStepId?: string;

  metadata: {
    workflowId: string;
    requestId: string;
    correlationId?: string;
    userId?: string;
    triggeredBy: 'api' | 'event' | 'schedule';
  };
}

interface StepExecutionState {
  id: string;
  agentId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

  input: Record<string, any>;
  output?: Record<string, any>;
  error?: {
    code: string;
    message: string;
  };

  startTime?: Date;
  endTime?: Date;
  duration?: number;

  retryCount: number;
  nextRetryAt?: Date;
}

export class WorkflowEngine {
  private logger: Logger;
  private workflows: Map<string, WorkflowDefinition> = new Map();
  private executions: Map<string, WorkflowExecutionState> = new Map();
  private agentRegistry: any;  // AgentRegistry
  private postgres: any;
  private redis: any;

  constructor(options: {
    logger: Logger;
    agentRegistry: any;
    postgres: any;
    redis: any;
  }) {
    this.logger = options.logger;
    this.agentRegistry = options.agentRegistry;
    this.postgres = options.postgres;
    this.redis = options.redis;
  }

  /**
   * Register a workflow definition
   */
  async registerWorkflow(definition: WorkflowDefinition): Promise<void> {
    this.workflows.set(definition.id, definition);

    // Persist to database
    await this.postgres.query(
      `INSERT INTO workflows (id, name, version, definition)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (id) DO UPDATE SET definition = $4`,
      [definition.id, definition.name, definition.version, JSON.stringify(definition)]
    );

    this.logger.info('Workflow registered', { workflowId: definition.id, name: definition.name });
  }

  /**
   * Execute a workflow
   */
  async execute(
    workflowId: string,
    input: Record<string, any>,
    metadata: {
      requestId: string;
      correlationId?: string;
      userId?: string;
      triggeredBy: 'api' | 'event' | 'schedule';
    }
  ): Promise<WorkflowExecutionState> {
    const workflow = this.workflows.get(workflowId);
    if (!workflow) {
      throw new Error(`Workflow not found: ${workflowId}`);
    }

    const executionId = `wf-${Date.now()}-${uuidv4().substring(0, 8)}`;

    const execution: WorkflowExecutionState = {
      id: executionId,
      definitionId: workflowId,
      status: 'running',
      startTime: new Date(),
      input,
      steps: new Map(),
      metadata: {
        workflowId,
        requestId: metadata.requestId,
        correlationId: metadata.correlationId || metadata.requestId,
        userId: metadata.userId,
        triggeredBy: metadata.triggeredBy,
      },
    };

    // Initialize step states
    for (const step of workflow.steps) {
      execution.steps.set(step.id, {
        id: step.id,
        agentId: step.agentId,
        status: 'pending',
        input: step.input,
        retryCount: 0,
      });
    }

    this.executions.set(executionId, execution);

    // Persist to database
    await this.persistExecution(execution);

    this.logger.info('Workflow execution started', {
      executionId,
      workflowId,
      requestId: metadata.requestId,
    });

    // Execute workflow asynchronously
    this.executeSteps(workflow, execution).catch(error => {
      this.logger.error('Workflow execution error', {
        executionId,
        error: error.message,
        requestId: metadata.requestId,
      });
    });

    return execution;
  }

  /**
   * Execute workflow steps sequentially
   */
  private async executeSteps(
    workflow: WorkflowDefinition,
    execution: WorkflowExecutionState
  ): Promise<void> {
    for (const stepDef of workflow.steps) {
      const stepState = execution.steps.get(stepDef.id)!;

      try {
        execution.currentStepId = stepDef.id;
        await this.executeStep(stepDef, stepState, execution);

        // Store step output
        if (stepDef.outputPath) {
          const pathParts = stepDef.outputPath.split('.');
          let current = execution.output || {};
          for (let i = 0; i < pathParts.length - 1; i++) {
            current[pathParts[i]] = current[pathParts[i]] || {};
            current = current[pathParts[i]];
          }
          current[pathParts[pathParts.length - 1]] = stepState.output;
          execution.output = execution.output || {};
        }

      } catch (error: any) {
        this.logger.error('Step execution failed', {
          stepId: stepDef.id,
          error: error.message,
          executionId: execution.id,
        });

        // Handle error policy
        if (stepDef.onError === 'fail') {
          execution.status = 'failed';
          execution.error = {
            stepId: stepDef.id,
            code: error.code || 'STEP_FAILED',
            message: error.message,
          };
          execution.endTime = new Date();
          await this.persistExecution(execution);
          throw error;

        } else if (stepDef.onError === 'continue') {
          stepState.status = 'skipped';
          continue;

        } else if (stepDef.onError === 'retry') {
          // Already retried in executeStep
          throw error;
        }
      }
    }

    // Workflow completed successfully
    execution.status = 'completed';
    execution.endTime = new Date();

    // Build final output using templates
    execution.output = this.buildOutput(workflow.outputs, execution);

    await this.persistExecution(execution);

    this.logger.info('Workflow execution completed', {
      executionId: execution.id,
      duration: execution.endTime.getTime() - execution.startTime.getTime(),
    });
  }

  /**
   * Execute a single step with retry logic
   */
  private async executeStep(
    stepDef: WorkflowStep,
    stepState: StepExecutionState,
    execution: WorkflowExecutionState
  ): Promise<void> {
    const maxAttempts = stepDef.retryPolicy?.maxAttempts || 3;
    const backoffMs = stepDef.retryPolicy?.backoffMs || 1000;
    const exponential = stepDef.retryPolicy?.exponential !== false;

    let lastError: any;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        stepState.status = 'running';
        stepState.startTime = new Date();
        stepState.retryCount = attempt - 1;

        // Resolve input templates
        const resolvedInput = this.resolveTemplates(stepDef.input, execution);

        // Execute agent through registry
        const output = await this.agentRegistry.execute(stepDef.agentId, resolvedInput, {
          workflowId: execution.id,
          stepId: stepDef.id,
          correlationId: execution.metadata.correlationId,
          requestId: execution.metadata.requestId,
        });

        stepState.output = output;
        stepState.status = 'completed';
        stepState.endTime = new Date();
        stepState.duration = stepState.endTime.getTime() - stepState.startTime!.getTime();

        this.logger.info('Step completed', {
          stepId: stepDef.id,
          executionId: execution.id,
          attempt,
          duration: stepState.duration,
        });

        return;

      } catch (error: any) {
        lastError = error;

        if (attempt < maxAttempts) {
          const delay = exponential ? backoffMs * Math.pow(2, attempt - 1) : backoffMs * attempt;
          stepState.nextRetryAt = new Date(Date.now() + delay);

          this.logger.warn('Step failed, retrying', {
            stepId: stepDef.id,
            executionId: execution.id,
            attempt,
            nextAttempt: attempt + 1,
            retryAfter: delay,
            error: error.message,
          });

          await new Promise(resolve => setTimeout(resolve, delay));

        } else {
          stepState.status = 'failed';
          stepState.endTime = new Date();
          stepState.error = {
            code: error.code || 'STEP_FAILED',
            message: error.message,
          };
        }
      }
    }

    throw lastError;
  }

  /**
   * Resolve template syntax in input
   * {{ steps.stepId.output.field }}
   * {{ params.fieldName }}
   */
  private resolveTemplates(
    input: Record<string, any>,
    execution: WorkflowExecutionState
  ): Record<string, any> {
    const resolved = { ...input };

    for (const [key, value] of Object.entries(resolved)) {
      if (typeof value === 'string' && value.includes('{{')) {
        // Simple template resolution
        let result = value;

        // Handle {{ steps.X.output }}
        result = result.replace(/\{\{\s*steps\.(\w+)\.output\s*\}\}/g, (match, stepId) => {
          const step = execution.steps.get(stepId);
          return step?.output ? JSON.stringify(step.output) : '';
        });

        // Handle {{ params.X }}
        result = result.replace(/\{\{\s*params\.(\w+)\s*\}\}/g, (match, paramName) => {
          return execution.input[paramName] || '';
        });

        resolved[key] = result;
      }
    }

    return resolved;
  }

  /**
   * Build final workflow output from template
   */
  private buildOutput(
    templates: Record<string, string>,
    execution: WorkflowExecutionState
  ): Record<string, any> {
    const output: Record<string, any> = {};

    for (const [key, template] of Object.entries(templates)) {
      // Simple template resolution for final outputs
      output[key] = this.resolveTemplates({ value: template }, execution).value;
    }

    return output;
  }

  /**
   * Get execution state
   */
  async getExecution(executionId: string): Promise<WorkflowExecutionState | null> {
    return this.executions.get(executionId) ||
      (await this.loadExecution(executionId));
  }

  /**
   * List executions
   */
  async listExecutions(workflowId: string, limit = 20): Promise<WorkflowExecutionState[]> {
    const rows = await this.postgres.query(
      `SELECT * FROM workflow_executions WHERE workflow_id = $1 ORDER BY start_time DESC LIMIT $2`,
      [workflowId, limit]
    );

    return rows.map(row => JSON.parse(row.execution_state));
  }

  /**
   * Cancel execution
   */
  async cancel(executionId: string): Promise<void> {
    const execution = this.executions.get(executionId);
    if (execution && execution.status === 'running') {
      execution.status = 'cancelled';
      execution.endTime = new Date();
      await this.persistExecution(execution);

      this.logger.info('Workflow cancelled', { executionId });
    }
  }

  /**
   * Persist execution to database
   */
  private async persistExecution(execution: WorkflowExecutionState): Promise<void> {
    const stepsMap = Object.fromEntries(execution.steps);

    await this.postgres.query(
      `INSERT INTO workflow_executions (id, workflow_id, status, execution_state, created_at, updated_at)
       VALUES ($1, $2, $3, $4, NOW(), NOW())
       ON CONFLICT (id) DO UPDATE SET status = $3, execution_state = $4, updated_at = NOW()`,
      [
        execution.id,
        execution.definitionId,
        execution.status,
        JSON.stringify({ ...execution, steps: stepsMap }),
      ]
    );
  }

  /**
   * Load execution from database
   */
  private async loadExecution(executionId: string): Promise<WorkflowExecutionState | null> {
    const row = await this.postgres.queryOne(
      `SELECT execution_state FROM workflow_executions WHERE id = $1`,
      [executionId]
    );

    if (!row) return null;

    const state = JSON.parse(row.execution_state);
    state.steps = new Map(Object.entries(state.steps));
    return state;
  }
}
