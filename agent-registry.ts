/**
 * Built-in Agent Registration
 *
 * Registers default SuperQwen agents as Motia orchestration steps
 */

import { Logger } from 'motia';
import * as researchAgent from './steps/agents/research-agent.step';
import * as analysisAgent from './steps/agents/analysis-agent.step';

export async function registerBuiltInAgents(registry: any, logger: Logger) {
  logger.info('Registering built-in agents...');

  try {
    // Register research agent
    const researchMetadata = {
      id: 'research-agent',
      name: 'research-agent',
      displayName: 'Research Agent',
      description: 'Comprehensive research using deep investigation patterns',
      version: '1.0.0',
      personaId: 'deep-research-agent',
      executionModes: ['background'],
      defaultModel: process.env.OLLAMA_MODEL || 'qwen:32b',
      capabilities: ['web-search', 'document-analysis', 'synthesis'],
      tags: ['research', 'investigation', 'analysis'],
      timeout: 120000,
      retryPolicy: {
        maxAttempts: 3,
        backoffMs: 2000,
        exponential: true,
      },
      resources: {
        cpu: '2',
        memory: '2Gi',
      },
      inputSchema: researchAgent.config.inputSchema,
      outputSchema: researchAgent.config.outputSchema,
      createdAt: new Date(),
      updatedAt: new Date(),
      status: 'active',
    };

    registry.register(researchMetadata, researchAgent.handler);
    logger.info('✅ Research agent registered', { agentId: 'research-agent' });

    // Register analysis agent
    const analysisMetadata = {
      id: 'analysis-agent',
      name: 'analysis-agent',
      displayName: 'Analysis Agent',
      description: 'Systematic analysis using structured thinking patterns',
      version: '1.0.0',
      personaId: 'system-architect',
      executionModes: ['background'],
      defaultModel: process.env.OLLAMA_MODEL || 'qwen:32b',
      capabilities: ['analysis', 'thinking', 'synthesis'],
      tags: ['analysis', 'thinking', 'investigation'],
      timeout: 60000,
      retryPolicy: {
        maxAttempts: 2,
        backoffMs: 1000,
        exponential: true,
      },
      resources: {
        cpu: '1',
        memory: '1Gi',
      },
      inputSchema: analysisAgent.config.inputSchema,
      outputSchema: analysisAgent.config.outputSchema,
      createdAt: new Date(),
      updatedAt: new Date(),
      status: 'active',
    };

    registry.register(analysisMetadata, analysisAgent.handler);
    logger.info('✅ Analysis agent registered', { agentId: 'analysis-agent' });

    logger.info('✅ All built-in agents registered successfully');
    return true;

  } catch (error: any) {
    logger.error('❌ Failed to register built-in agents', {
      error: error.message,
      stack: error.stack,
    });
    throw error;
  }
}

/**
 * List all registered agents
 */
export function listBuiltInAgents() {
  return [
    {
      id: 'research-agent',
      name: 'Research Agent',
      description: 'Comprehensive research',
      type: 'agent',
    },
    {
      id: 'analysis-agent',
      name: 'Analysis Agent',
      description: 'Systematic analysis',
      type: 'agent',
    },
  ];
}
