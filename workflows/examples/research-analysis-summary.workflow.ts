/**
 * Research-Analysis-Summary Workflow
 *
 * Three-step workflow demonstrating agent coordination:
 * 1. Research a topic comprehensively
 * 2. Analyze findings systematically
 * 3. Generate executive summary
 */

import { WorkflowDefinition } from '../workflow-engine';

export const ResearchAnalysisSummaryWorkflow: WorkflowDefinition = {
  id: 'research-analysis-summary',
  name: 'Research, Analysis & Summary',
  version: '1.0.0',
  description: 'Complete research-to-report workflow: deep research → systematic analysis → executive summary',

  steps: [
    {
      id: 'research-step',
      agentId: 'research-agent',
      input: {
        query: '{{ params.topic }}',
        depth: '{{ params.researchDepth | default("deep") }}',
        maxHops: '{{ params.maxHops | default(4) }}',
      },
      timeout: 120000,  // 2 minutes for research
      retryPolicy: {
        maxAttempts: 3,
        backoffMs: 2000,
        exponential: true,
      },
      onError: 'fail',
      outputPath: 'research',
    },

    {
      id: 'analysis-step',
      agentId: 'analysis-agent',
      input: {
        subject: '{{ steps.research-step.output }}',
        framework: 'sequential',
        depth: 'deep',
        format: 'structured',
      },
      condition: '{{ steps.research-step.output.confidence > 0.6 }}',
      timeout: 90000,  // 1.5 minutes for analysis
      retryPolicy: {
        maxAttempts: 2,
        backoffMs: 1000,
      },
      onError: 'fail',
      outputPath: 'analysis',
    },

    {
      id: 'summary-step',
      agentId: 'business-panel-agent',
      input: {
        content: '{{ steps.analysis-step.output }}',
        findings: '{{ steps.research-step.output.findings }}',
        format: 'executive-summary',
        audience: 'business-leadership',
      },
      timeout: 60000,  // 1 minute for summary
      retryPolicy: {
        maxAttempts: 2,
        backoffMs: 1000,
      },
      onError: 'continue',  // Continue even if summary fails
      outputPath: 'summary',
    },
  ],

  outputs: {
    topic: '{{ params.topic }}',
    research: '{{ steps.research-step.output }}',
    analysis: '{{ steps.analysis-step.output }}',
    summary: '{{ steps.summary-step.output }}',
    completedAt: '{{ now() }}',
  },

  metadata: {
    owner: 'research-team',
    tags: ['research', 'analysis', 'reporting', 'business-intelligence'],
  },
};

/**
 * Execution Example:
 *
 * POST /api/workflows/research-analysis-summary/execute
 *
 * {
 *   "params": {
 *     "topic": "AI Orchestration Platforms 2025",
 *     "researchDepth": "deep",
 *     "maxHops": 5
 *   }
 * }
 *
 * Response:
 * {
 *   "workflowId": "wf-1730896200000-a1b2c3d4",
 *   "status": "running",
 *   "currentStep": "research-step",
 *   "stateUrl": "/api/workflows/research-analysis-summary/wf-1730896200000-a1b2c3d4"
 * }
 *
 * Poll for completion:
 * GET /api/workflows/research-analysis-summary/wf-1730896200000-a1b2c3d4
 *
 * Final output includes:
 * - research.findings: Array of key findings
 * - research.sources: Researched sources with relevance scores
 * - analysis.keyPoints: Analyzed insights
 * - analysis.risks: Identified risks/challenges
 * - analysis.opportunities: Identified opportunities
 * - summary: Executive summary for leadership
 */
