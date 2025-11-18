/**
 * CI/CD Pipeline Agent - Pipeline automation using qwen3-coder:480b
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'CICDPipelineAgent',
  description: 'CI/CD pipeline generation and optimization',
  flows: ['vps-orchestration', 'automation'],
  method: 'POST',
  path: '/api/agents/cicd-pipeline/execute',
  emits: [],
  bodySchema: z.object({
    platform: z.enum(['gitlab', 'github', 'generic']).default('gitlab'),
    language: z.string().default('python'),
  }),
  responseSchema: {
    200: z.object({
      pipeline_yaml: z.string(),
      stages: z.array(z.string()),
      estimated_duration: z.string(),
      metadata: z.object({ duration_ms: z.number(), model_used: z.string() }),
    }),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const startTime = Date.now();
  const ollamaApiKey = process.env.OLLAMA_API_KEY || 'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

  try {
    const response = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${ollamaApiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'qwen3-coder:480b',
        prompt: `Generate ${req.body.platform} CI/CD pipeline for ${req.body.language} project with build, test, deploy stages.`,
        stream: false,
        options: { temperature: 0.3, num_predict: 1000 },
      }),
    });

    const result = await response.json();

    return {
      status: 200,
      body: {
        pipeline_yaml: result.response || '# CI/CD pipeline',
        stages: ['build', 'test', 'deploy'],
        estimated_duration: '5-10 minutes',
        metadata: { duration_ms: Date.now() - startTime, model_used: 'qwen3-coder:480b' },
      },
    };
  } catch (error: any) {
    return { status: 500, body: { error: error.message } };
  }
};
