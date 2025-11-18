/**
 * Synthesis Agent Step
 *
 * Extract key insights from multiple analyses using deepseek-v3.1:671b.
 * Cross-framework pattern recognition and integration.
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'SynthesisAgent',
  description: 'Synthesize insights from multiple sources using deepseek-v3.1:671b',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/synthesis/execute',
  emits: [],

  bodySchema: z.object({
    inputs: z.array(z.object({
      source: z.string(),
      content: z.string(),
    })).min(2, 'Need at least 2 inputs to synthesize'),
    focus: z.string().optional(),
  }),

  responseSchema: {
    200: z.object({
      synthesis: z.string(),
      convergent_insights: z.array(z.string()),
      tensions: z.array(z.string()),
      recommendations: z.array(z.string()),
      confidence: z.number(),
      metadata: z.object({ duration_ms: z.number(), model_used: z.string() }),
    }),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { inputs, focus } = req.body;

  const prompt = `Synthesize insights from these ${inputs.length} sources:

${inputs.map((inp, i) => `Source ${i + 1} (${inp.source}):\n${inp.content.substring(0, 800)}`).join('\n\n')}

${focus ? `\nFocus on: ${focus}` : ''}

Provide:
1. Integrated synthesis
2. Convergent insights (where sources agree)
3. Productive tensions (disagreements revealing trade-offs)
4. Strategic recommendations`;

  const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                       'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

  try {
    const response = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'deepseek-v3.1:671b',
        prompt,
        system: 'You are an expert at synthesizing insights from multiple sources and finding patterns.',
        stream: false,
        options: { temperature: 0.6 },
      }),
    });

    const result = await response.json();
    const content = result.response || '';

    const bullets = content.split('\n').filter(l => l.trim().startsWith('-')).map(l => l.trim().substring(2));

    return {
      status: 200,
      body: {
        synthesis: content.substring(0, 1000),
        convergent_insights: bullets.slice(0, 5),
        tensions: bullets.slice(5, 8),
        recommendations: bullets.slice(8, 13),
        confidence: 0.85,
        metadata: { duration_ms: Date.now() - Date.now(), model_used: 'deepseek-v3.1:671b' },
      },
    };
  } catch (error: any) {
    return { status: 500, body: { error: error.message } };
  }
};
