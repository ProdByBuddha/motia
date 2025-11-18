/**
 * Analysis Agent Step
 *
 * Implements systematic analysis capability as a Motia step
 * Coordinates with Sequential thinking engine for complex analysis
 */

import { z } from 'zod';
import { Pool } from 'pg';

let pgPool: any = null;

function getPgPool() {
  if (!pgPool) {
    pgPool = new Pool({
      host: process.env.POSTGRES_HOST || 'postgres',
      port: parseInt(process.env.POSTGRES_PORT || '5432'),
      database: process.env.POSTGRES_DB || 'billionmail',
      user: process.env.POSTGRES_USER || 'postgres',
      password: process.env.POSTGRES_PASSWORD || 'postgres',
    });
  }
  return pgPool;
}

export const config = {
  type: 'api',
  name: 'AnalysisAgent',
  description: 'Systematic analysis using structured thinking patterns',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/analysis/execute',
  emits: [],

  bodySchema: z.object({
    subject: z.string().min(10).describe('What to analyze'),
    framework: z.enum(['sequential', 'comparative', 'causal', 'systems']).default('sequential'),
    depth: z.enum(['surface', 'moderate', 'deep']).default('moderate'),
    format: z.enum(['structured', 'narrative', 'bullet_points']).default('structured'),
  }),

  responseSchema: {
    200: z.object({
      subject: z.string(),
      framework: z.string(),
      analysis: z.string().describe('Main analysis content'),
      keyPoints: z.array(z.string()).describe('Distilled insights'),
      risks: z.array(z.string()).optional().describe('Identified risks'),
      opportunities: z.array(z.string()).optional().describe('Identified opportunities'),
      nextSteps: z.array(z.string()).optional().describe('Recommended actions'),
      confidence: z.number().min(0).max(1),
    }),
    400: z.object({ error: z.string() }),
    500: z.object({ error: z.string(), details: z.any().optional() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { subject, framework, depth, format } = req.body;

  logger.info('Analysis agent starting', {
    subject: subject.substring(0, 50),
    framework,
    depth,
  });

  const startTime = Date.now();

  try {
    const postgres = getPgPool();

    // Log analysis request for audit trail
    try {
      await postgres.query(
        `INSERT INTO analysis_requests (workflow_id, subject, framework, depth, status, created_at)
         VALUES ($1, $2, $3, $4, 'running', NOW())`,
        ['wf-phase1', subject, framework, depth]
      );
    } catch (e) {
      logger.warn('Could not log analysis request', { error: (e as any).message });
    }

    // Mock analysis result for Phase 1 demo
    // In production: await superqwen.execute('analysis-agent', {...})
    const analysisResult = {
      analysis: `Comprehensive analysis of "${subject.substring(0, 30)}..." using ${framework} framework at ${depth} depth. This analysis demonstrates the Phase 1 implementation of the Motia-SuperQwen orchestration system.`,
      insights: [
        'First key insight from analysis',
        'Second pattern identified',
        'Third strategic recommendation',
      ],
      risks: [
        'Implementation complexity',
        'Integration challenges',
      ],
      opportunities: [
        'Significant scalability potential',
        'Market differentiation opportunity',
      ],
      recommendations: [
        'Proceed with Phase 2 implementation',
        'Establish performance baselines',
      ],
      confidence: 0.82,
    };

    // Parse and structure output
    const output = {
      subject,
      framework,
      analysis: analysisResult.analysis,
      keyPoints: analysisResult.insights || [],
      risks: analysisResult.risks || [],
      opportunities: analysisResult.opportunities || [],
      nextSteps: analysisResult.recommendations || [],
      confidence: analysisResult.confidence || 0.75,
    };

    // Log completion
    const duration = Date.now() - startTime;
    try {
      await postgres.query(
        `UPDATE analysis_requests SET status = 'completed', duration = $1, key_points_count = $2
         WHERE workflow_id = $3 AND subject = $4`,
        [duration, output.keyPoints.length, 'wf-phase1', subject]
      );
    } catch (e) {
      logger.warn('Could not update analysis completion', { error: (e as any).message });
    }

    logger.info('Analysis agent completed', {
      keyPointCount: output.keyPoints.length,
      riskCount: output.risks.length,
      opportunityCount: output.opportunities.length,
      confidence: output.confidence,
      duration,
    });

    return {
      status: 200,
      body: output,
    };

  } catch (error: any) {
    logger.error('Analysis agent failed', {
      error: error.message,
      stack: error.stack,
      subject: subject.substring(0, 50),
    });

    return {
      status: 500,
      body: {
        error: 'Analysis execution failed',
        details: {
          framework,
          depth,
          message: error.message,
        },
      },
    };
  }
};

/**
 * Example usage in workflow:
 *
 * {
 *   id: 'analysis-step',
 *   agentId: 'analysis-agent',
 *   input: {
 *     subject: '{{ steps.research.output.findings | join(",") }}',
 *     framework: 'sequential',
 *     depth: 'deep',
 *   },
 * }
 */
