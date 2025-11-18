/**
 * Workflow Registry
 *
 * Manages workflow definitions and provides execution interface
 */

import { Logger } from 'motia';
import { WorkflowEngine } from './workflows/workflow-engine';
import * as researchAnalysisWorkflow from './workflows/examples/research-analysis-summary.workflow';

export async function registerBuiltInWorkflows(
  engine: WorkflowEngine,
  logger: Logger
) {
  logger.info('Registering built-in workflows...');

  try {
    // Register research-analysis-summary workflow
    await engine.registerWorkflow(researchAnalysisWorkflow.ResearchAnalysisSummaryWorkflow);
    logger.info('✅ Workflow registered', {
      workflowId: 'research-analysis-summary',
      steps: 3,
    });

    logger.info('✅ All workflows registered successfully');
    return true;

  } catch (error: any) {
    logger.error('❌ Failed to register workflows', {
      error: error.message,
      stack: error.stack,
    });
    throw error;
  }
}

/**
 * List all available workflows
 */
export function listBuiltInWorkflows() {
  return [
    {
      id: 'research-analysis-summary',
      name: 'Research, Analysis & Summary',
      description: 'Research topic → analyze findings → generate summary',
      steps: 3,
      status: 'active',
    },
  ];
}
