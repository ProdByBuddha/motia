/**
 * Planning Agent Step
 *
 * Strategic planning and execution roadmap generation using deepseek-v3.1:671b.
 * Creates detailed plans with dependencies, timelines, and resource allocation.
 */

import { z } from 'zod';
import { createClient } from 'redis';
import { Pool } from 'pg';

let redisClient: any = null;
let pgPool: any = null;

async function getRedisClient() {
  if (!redisClient) {
    redisClient = createClient({
      socket: {
        host: process.env.REDIS_HOST || 'redis',
        port: parseInt(process.env.REDIS_PORT || '6379'),
      },
      password: process.env.REDIS_PASSWORD,
    });
    await redisClient.connect();
  }
  return redisClient;
}

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
  name: 'PlanningAgent',
  description: 'Strategic planning using deepseek-v3.1:671b (671B parameters)',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/planning/execute',
  emits: [],

  bodySchema: z.object({
    objective: z.string().min(10, 'Objective must be at least 10 characters'),
    constraints: z.array(z.string()).optional().describe('Constraints and limitations'),
    available_resources: z.array(z.string()).optional().describe('Available resources'),
    timeline: z.string().optional().describe('Target timeline'),
  }),

  responseSchema: {
    200: z.object({
      objective: z.string(),
      total_steps: z.number(),
      estimated_duration: z.string(),
      steps: z.array(z.object({
        sequence: z.number(),
        action: z.string(),
        duration_estimate: z.string().optional(),
        dependencies: z.array(z.number()).describe('Prerequisite step indices'),
        success_criteria: z.array(z.string()),
      })),
      risks: z.array(z.string()),
      contingencies: z.array(z.string()),
      metadata: z.object({
        duration_ms: z.number(),
        model_used: z.string(),
      }).optional(),
    }),
    400: z.object({ error: z.string() }),
    500: z.object({ error: z.string(), details: z.any().optional() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { objective, constraints, available_resources, timeline } = req.body;

  logger.info('Planning agent starting', {
    objective: objective.substring(0, 50),
    constraintsCount: constraints?.length || 0,
  });

  const startTime = Date.now();

  try {
    // Build planning prompt
    const prompt = `Create a detailed execution plan for:

Objective: ${objective}

${constraints && constraints.length > 0 ? `Constraints:\n${constraints.map(c => `- ${c}`).join('\n')}\n` : ''}
${available_resources && available_resources.length > 0 ? `Available Resources:\n${available_resources.map(r => `- ${r}`).join('\n')}\n` : ''}
${timeline ? `Target Timeline: ${timeline}\n` : ''}

Provide a comprehensive execution plan with:
1. Numbered sequential steps
2. Duration estimate for each step
3. Dependencies between steps
4. Success criteria for each step
5. Overall timeline estimate
6. Risk assessment
7. Contingency plans

Format as:
Step 1: [Action] (Duration: X) [Dependencies: none] [Success: criteria]
Step 2: [Action] (Duration: X) [Dependencies: 1] [Success: criteria]
...

Risks: [list]
Contingencies: [list]
Total Duration: [estimate]`;

    // Call Ollama Cloud (deepseek-v3.1:671b for strategic planning)
    const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                         'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    logger.info('Calling deepseek-v3.1:671b for planning');

    const ollamaResponse = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'deepseek-v3.1:671b',
        prompt: prompt,
        system: 'You are a strategic planner and project manager. Create detailed, realistic execution plans with clear dependencies and success criteria.',
        stream: false,
        options: {
          temperature: 0.6,
          num_predict: 2500,
        },
      }),
    });

    if (!ollamaResponse.ok) {
      logger.error('Ollama Cloud error', { status: ollamaResponse.status });
      throw new Error('Planning generation failed');
    }

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    logger.info('Plan generated', { responseLength: responseText.length });

    // Parse steps from response
    const steps: any[] = [];
    const lines = responseText.split('\n');

    for (const line of lines) {
      const trimmed = line.trim();

      // Match: "Step 1: Action (Duration: 2 hours) [Dependencies: none] [Success: criteria]"
      const stepMatch = trimmed.match(/Step\s+(\d+):\s*(.+?)(?:\s*\(Duration:\s*([^)]+)\))?/i);

      if (stepMatch) {
        const sequence = parseInt(stepMatch[1]);
        const action = stepMatch[2].replace(/\[.*?\]/g, '').trim();
        const durationEstimate = stepMatch[3] || 'TBD';

        // Extract dependencies
        const depsMatch = trimmed.match(/Dependencies:\s*([^\]]+)/i);
        const dependencies: number[] = [];

        if (depsMatch && depsMatch[1].toLowerCase() !== 'none') {
          const depNums = depsMatch[1].match(/\d+/g);
          if (depNums) {
            dependencies.push(...depNums.map(n => parseInt(n)));
          }
        }

        // Extract success criteria
        const successMatch = trimmed.match(/Success:\s*([^\]]+)/i);
        const successCriteria = successMatch
          ? [successMatch[1].trim()]
          : ['Step completed successfully'];

        steps.push({
          sequence,
          action,
          duration_estimate: durationEstimate,
          dependencies,
          success_criteria: successCriteria,
        });
      }
    }

    // Extract risks
    const risks: string[] = [];
    let inRisksSection = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (/^Risks?:/i.test(trimmed)) {
        inRisksSection = true;
        continue;
      }

      if (/^Contingencies?:|^Total Duration:/i.test(trimmed)) {
        inRisksSection = false;
      }

      if (inRisksSection && (trimmed.startsWith('-') || trimmed.startsWith('*'))) {
        risks.push(trimmed.replace(/^[-*]\s*/, ''));
      }
    }

    // Extract contingencies
    const contingencies: string[] = [];
    let inContSection = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (/^Contingencies?:/i.test(trimmed)) {
        inContSection = true;
        continue;
      }

      if (/^Total Duration:|^Conclusion:/i.test(trimmed)) {
        inContSection = false;
      }

      if (inContSection && (trimmed.startsWith('-') || trimmed.startsWith('*'))) {
        contingencies.push(trimmed.replace(/^[-*]\s*/, ''));
      }
    }

    // Extract total duration
    const durationMatch = responseText.match(/Total Duration:\s*([^\n]+)/i);
    const estimatedDuration = durationMatch ? durationMatch[1].trim() : 'To be determined';

    const duration = Date.now() - startTime;

    const result = {
      objective,
      total_steps: steps.length,
      estimated_duration: estimatedDuration,
      steps: steps.sort((a, b) => a.sequence - b.sequence),
      risks: risks.slice(0, 10),
      contingencies: contingencies.slice(0, 10),
      metadata: {
        duration_ms: duration,
        model_used: 'deepseek-v3.1:671b',
      },
    };

    // Log to audit
    const postgres = getPgPool();
    try {
      await postgres.query(
        `INSERT INTO agent_executions (
          agent_id, capability, query, findings_count,
          sources_count, confidence, duration_ms, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())`,
        [
          'planning-agent',
          'PLANNING',
          objective,
          steps.length,
          risks.length,
          1.0,
          duration,
        ]
      );
    } catch (e) {
      logger.warn('Audit logging failed', { error: (e as Error).message });
    }

    logger.info('Planning agent completed', {
      totalSteps: steps.length,
      risks: risks.length,
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('Planning agent failed', {
      error: error.message,
      stack: error.stack,
    });

    return {
      status: 500,
      body: {
        error: 'Planning generation failed',
        details: {
          objective,
          message: error.message,
        },
      },
    };
  }
};
