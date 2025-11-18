/**
 * Summarization Agent Step
 *
 * Fast summarization using gpt-oss:20b (20B parameters).
 * Extracts key insights and creates executive summaries.
 */

import { z } from 'zod';
import { createClient } from 'redis';

let redisClient: any = null;

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

export const config = {
  type: 'api',
  name: 'SummarizationAgent',
  description: 'Fast summarization using gpt-oss:20b (20B parameters)',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/summarization/execute',
  emits: [],

  bodySchema: z.object({
    content: z.string().min(50, 'Content must be at least 50 characters'),
    summary_type: z.enum(['executive', 'technical', 'bullet_points', 'abstract']).default('executive'),
    max_length: z.number().optional().describe('Max summary length in words'),
    focus_areas: z.array(z.string()).optional(),
  }),

  responseSchema: {
    200: z.object({
      original_length: z.number(),
      summary: z.string(),
      key_points: z.array(z.string()),
      summary_length: z.number(),
      compression_ratio: z.number(),
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
  const { content, summary_type, max_length, focus_areas } = req.body;

  logger.info('Summarization agent starting', {
    summary_type,
    contentLength: content.length,
  });

  const startTime = Date.now();

  try {
    const maxWords = max_length || (summary_type === 'executive' ? 250 : 500);

    const prompt = `Summarize the following content as ${summary_type === 'bullet_points' ? 'bullet points' : summary_type + ' summary'}:

${content.substring(0, 5000)}

${focus_areas && focus_areas.length > 0 ? `Focus on:\n${focus_areas.map(f => `- ${f}`).join('\n')}\n` : ''}

Requirements:
- Maximum ${maxWords} words
- Extract key points
- ${summary_type === 'executive' ? 'Executive-level clarity' : ''}
- ${summary_type === 'technical' ? 'Technical accuracy' : ''}
- ${summary_type === 'bullet_points' ? 'Concise bullet format' : ''}

Provide:
1. Summary (${maxWords} words max)
2. Key Points (5-7 bullet points)`;

    const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                         'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    logger.info('Calling gpt-oss:20b for summarization');

    const ollamaResponse = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gpt-oss:20b',
        prompt: prompt,
        system: 'You are an expert at extracting key insights and creating clear summaries.',
        stream: false,
        options: {
          temperature: 0.5,
          num_predict: 1000,
        },
      }),
    });

    if (!ollamaResponse.ok) {
      throw new Error('Summarization failed');
    }

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    // Extract summary (before "Key Points" section)
    const keyPointsMatch = responseText.match(/Key Points?:/i);
    const summary = keyPointsMatch
      ? responseText.substring(0, keyPointsMatch.index).trim()
      : responseText.trim();

    // Extract key points
    const keyPoints: string[] = [];
    const lines = responseText.split('\n');
    let inKeyPoints = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (/^Key Points?:/i.test(trimmed)) {
        inKeyPoints = true;
        continue;
      }

      if (inKeyPoints && (trimmed.startsWith('-') || trimmed.startsWith('*') || /^\d+\./.test(trimmed))) {
        keyPoints.push(trimmed.replace(/^[-*\d.]\s*/, ''));
      }
    }

    const originalWords = content.split(/\s+/).length;
    const summaryWords = summary.split(/\s+/).length;
    const compressionRatio = originalWords > 0 ? summaryWords / originalWords : 0;

    const duration = Date.now() - startTime;

    const result = {
      original_length: content.length,
      summary,
      key_points: keyPoints,
      summary_length: summaryWords,
      compression_ratio: parseFloat(compressionRatio.toFixed(2)),
      metadata: {
        duration_ms: duration,
        model_used: 'gpt-oss:20b',
      },
    };

    logger.info('Summarization completed', {
      originalWords,
      summaryWords,
      compression: compressionRatio.toFixed(2),
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('Summarization agent failed', {
      error: error.message,
    });

    return {
      status: 500,
      body: {
        error: 'Summarization failed',
        details: { message: error.message },
      },
    };
  }
};
