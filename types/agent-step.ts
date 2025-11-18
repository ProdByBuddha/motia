/**
 * Agent Step Types and Interfaces
 *
 * Defines the contract for SuperQwen agents integrated as Motia steps
 */

import { z } from 'zod';

/**
 * Agent Step Configuration
 * Metadata about the agent and how it should be orchestrated
 */
export interface AgentStepConfig {
  type: 'agent';
  name: string;
  description: string;

  // SuperQwen integration
  agent: string;  // Agent name/identifier
  persona?: string;  // SuperQwen persona

  // Execution configuration
  executionMode?: 'conversational' | 'background';  // Default: background
  timeout?: number;  // Milliseconds (default: 60000)
  retryPolicy?: {
    maxAttempts?: number;  // Default: 3
    backoffMs?: number;  // Default: 1000
    exponential?: boolean;  // Default: true
  };

  // Resource constraints
  resources?: {
    cpu?: string;  // e.g., '1'
    memory?: string;  // e.g., '1Gi'
  };

  // I/O schemas
  inputSchema?: z.ZodType<any>;
  outputSchema?: z.ZodType<any>;

  // Metadata
  tags?: string[];
  flows?: string[];  // Motia flows this step belongs to
}

/**
 * Agent Step Handler Context
 * Runtime context available to agent step handlers
 */
export interface AgentStepContext {
  logger: {
    info(msg: string, meta?: Record<string, any>): void;
    warn(msg: string, meta?: Record<string, any>): void;
    error(msg: string, meta?: Record<string, any>): void;
    debug(msg: string, meta?: Record<string, any>): void;
  };

  // SuperQwen runtime
  superqwen: {
    execute(agent: string, input: any): Promise<any>;
    conversate(agent: string, message: string, context?: any): Promise<string>;
  };

  // State/cache
  redis: {
    get(key: string): Promise<any>;
    set(key: string, value: any, ttl?: number): Promise<void>;
    delete(key: string): Promise<void>;
  };

  // Database
  postgres: {
    query(sql: string, params?: any[]): Promise<any[]>;
    queryOne(sql: string, params?: any[]): Promise<any>;
  };

  // Workflow coordination
  workflow: {
    getCurrentWorkflowId(): string;
    getStepInput(stepId: string): any;
    setStepOutput(stepId: string, output: any): Promise<void>;
  };

  // Request context
  requestId: string;
  correlationId?: string;
  userId?: string;
}

/**
 * Agent Step Input/Output
 */
export interface AgentStepRequest {
  input: Record<string, any>;
  context?: {
    workflowId?: string;
    stepId?: string;
    correlationId?: string;
  };
}

export interface AgentStepResponse {
  status: 'success' | 'failure';
  output?: Record<string, any>;
  error?: string;
  metadata?: {
    duration: number;  // milliseconds
    retried: boolean;
    retryCount: number;
  };
}

/**
 * Agent Step Handler Function Type
 */
export type AgentStepHandler = (
  input: Record<string, any>,
  context: AgentStepContext
) => Promise<Record<string, any>>;

/**
 * Agent Metadata
 * Information about a registered agent
 */
export interface AgentMetadata {
  id: string;
  name: string;
  displayName?: string;
  description: string;
  version: string;

  // SuperQwen integration
  personaId: string;
  executionModes: ('conversational' | 'background')[];
  defaultModel: string;

  // Capabilities
  capabilities: string[];
  tags: string[];

  // Configuration
  timeout: number;
  retryPolicy: {
    maxAttempts: number;
    backoffMs: number;
    exponential: boolean;
  };

  resources: {
    cpu: string;
    memory: string;
  };

  // I/O
  inputSchema: any;  // JSON schema
  outputSchema: any;  // JSON schema

  // Lifecycle
  createdAt: Date;
  updatedAt: Date;
  status: 'active' | 'inactive' | 'deprecated';
}

/**
 * Workflow Step Reference
 * How agents are used in workflows
 */
export interface WorkflowStepReference {
  id: string;
  agentId: string;

  // Input binding
  input: Record<string, any> | string;  // Can use {{ }} template syntax

  // Conditional execution
  condition?: string;  // Boolean expression

  // Error handling
  onError?: 'fail' | 'continue' | 'retry' | 'alternate_step';
  alternateStep?: string;

  // Execution policy
  timeout?: number;
  retryPolicy?: {
    maxAttempts: number;
    backoffMs: number;
  };

  // Output handling
  outputPath?: string;  // Where to store output in workflow state
}

/**
 * Agent Execution Record
 * Persisted execution history
 */
export interface AgentExecutionRecord {
  id: string;
  agentId: string;
  status: 'pending' | 'running' | 'success' | 'failure';

  input: Record<string, any>;
  output?: Record<string, any>;
  error?: {
    code: string;
    message: string;
    details?: any;
  };

  workflowId?: string;
  stepId?: string;

  startTime: Date;
  endTime?: Date;
  duration?: number;  // milliseconds

  retryCount: number;
  nextRetryAt?: Date;

  metadata: {
    userId?: string;
    requestId: string;
    correlationId?: string;
  };
}

/**
 * Agent Registry
 * Service for discovering and managing agents
 */
export interface AgentRegistry {
  register(metadata: AgentMetadata, handler: AgentStepHandler): void;
  unregister(agentId: string): void;

  getAgent(agentId: string): AgentMetadata;
  listAgents(filter?: { tag?: string; status?: string }): AgentMetadata[];

  execute(agentId: string, input: any, context: AgentStepContext): Promise<any>;
}

/**
 * Common Agent Configurations (Templates)
 */

export const RESEARCH_AGENT_CONFIG: Partial<AgentStepConfig> = {
  type: 'agent',
  persona: 'deep-research-agent',
  executionMode: 'background',
  timeout: 120000,  // 2 minutes for research
  retryPolicy: {
    maxAttempts: 3,
    backoffMs: 2000,
    exponential: true,
  },
  resources: {
    cpu: '2',
    memory: '2Gi',
  },
};

export const ANALYSIS_AGENT_CONFIG: Partial<AgentStepConfig> = {
  type: 'agent',
  persona: 'system-architect',
  executionMode: 'background',
  timeout: 60000,  // 1 minute for analysis
  retryPolicy: {
    maxAttempts: 2,
    backoffMs: 1000,
  },
  resources: {
    cpu: '1',
    memory: '1Gi',
  },
};

export const BUSINESS_AGENT_CONFIG: Partial<AgentStepConfig> = {
  type: 'agent',
  persona: 'business-panel-expert',
  executionMode: 'background',
  timeout: 90000,  // 1.5 minutes
  retryPolicy: {
    maxAttempts: 2,
    backoffMs: 1000,
  },
  resources: {
    cpu: '1',
    memory: '1Gi',
  },
};
