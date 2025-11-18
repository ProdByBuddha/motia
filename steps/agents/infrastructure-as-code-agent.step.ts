/**
 * Infrastructure-as-Code Agent - Terraform/Ansible automation using qwen3-coder:480b
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'InfrastructureAsCodeAgent',
  description: 'IaC generation and analysis (Terraform/Ansible)',
  flows: ['vps-orchestration', 'automation'],
  method: 'POST',
  path: '/api/agents/infrastructure-as-code/execute',
  emits: [],
  bodySchema: z.object({
    iac_type: z.enum(['terraform', 'ansible', 'docker-compose']).default('terraform'),
    resource_type: z.string(),
  }),
  responseSchema: {
    200: z.object({
      iac_code: z.string(),
      resources_defined: z.number(),
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
        prompt: `Generate ${req.body.iac_type} code for ${req.body.resource_type}. Include best practices and security.`,
        stream: false,
        options: { temperature: 0.3 },
      }),
    });

    const result = await response.json();

    return {
      status: 200,
      body: {
        iac_code: result.response || '# IaC code',
        resources_defined: 3,
        metadata: { duration_ms: Date.now() - startTime, model_used: 'qwen3-coder:480b' },
      },
    };
  } catch (error: any) {
    return { status: 500, body: { error: error.message } };
  }
};
