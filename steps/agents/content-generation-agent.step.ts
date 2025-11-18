/**
 * Content Generation Agent Step
 *
 * Generate blog posts, articles, and content using gpt-oss:120b.
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'ContentGenerationAgent',
  description: 'Content generation using gpt-oss:120b',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/content-generation/execute',
  emits: [],

  bodySchema: z.object({
    topic: z.string().min(5),
    content_type: z.enum(['blog', 'article', 'tutorial', 'guide']).default('article'),
    audience: z.string().default('general'),
    tone: z.enum(['professional', 'casual', 'technical']).default('professional'),
    length: z.enum(['short', 'medium', 'long']).default('medium'),
  }),

  responseSchema: {
    200: z.object({
      title: z.string(),
      content: z.string(),
      word_count: z.number(),
      sections: z.array(z.string()),
      metadata: z.object({
        duration_ms: z.number(),
        model_used: z.string(),
      }),
    }),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { topic, content_type, audience, tone, length } = req.body;

  const wordTargets = { short: 500, medium: 1000, long: 2000 };
  const targetWords = wordTargets[length];

  const prompt = `Write a ${length} ${content_type} about: ${topic}

Audience: ${audience}
Tone: ${tone}
Target length: ~${targetWords} words

Include:
- Engaging title
- Clear sections
- ${content_type === 'tutorial' ? 'Step-by-step instructions' : ''}
- ${content_type === 'blog' ? 'Personal insights' : ''}
- Conclusion`;

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
        model: 'gpt-oss:120b',
        prompt,
        stream: false,
        options: { temperature: 0.7, num_predict: targetWords * 2 },
      }),
    });

    const result = await response.json();
    const content = result.response || '';
    const titleMatch = content.match(/^#\s*(.+)$/m);
    const title = titleMatch ? titleMatch[1] : topic;

    const sections = content.match(/^##\s*(.+)$/gm) || [];

    return {
      status: 200,
      body: {
        title,
        content,
        word_count: content.split(/\s+/).length,
        sections: sections.map(s => s.replace(/^##\s*/, '')),
        metadata: {
          duration_ms: Date.now() - Date.now(),
          model_used: 'gpt-oss:120b',
        },
      },
    };
  } catch (error: any) {
    return { status: 500, body: { error: error.message } };
  }
};
