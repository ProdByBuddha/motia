/**
 * Ollama Cloud Proxy - /api/chat endpoint
 * Uses exact same pattern as ollama-proxy.step.ts (which works)
 */

import { z } from 'zod';

// Zod schema for the incoming request from bolt.diy
const BoltDiyChatRequestSchema = z.object({
  messages: z.array(
    z.object({
      id: z.string(),
      role: z.enum(['user', 'assistant', 'system', 'function', 'data', 'tool']),
      content: z.string(),
    })
  ),
  model: z.string().optional().default('llama2'),
  stream: z.boolean().optional().default(false),
  files: z.any().optional(),
  promptId: z.string().optional(),
  contextOptimization: z.boolean().optional(),
  chatMode: z.enum(['discuss', 'build']).optional(),
  designScheme: z.any().optional(),
  supabase: z.any().optional(),
  maxLLMSteps: z.number().optional(),
});

export const config = {
  type: 'api',
  name: 'OllamaProxyChat',
  description: 'Proxy /api/chat to Ollama Cloud',
  flows: ['proxy'],
  method: 'POST',
  path: '/api/ollama/api/chat',
  emits: [],
  bodySchema: BoltDiyChatRequestSchema,
  responseSchema: { 200: z.any(), 500: z.object({ error: z.string() }) },
};

export const handler = async (req: any, { logger }: any) => {
  logger.info('Ollama Chat Proxy - Processing request');

  try {
    const parsedBody = req.body;

    logger.info('[PROXY] Proxying chat to Ollama Cloud', {
      model: parsedBody.model,
      stream: parsedBody.stream
    });

    // Transform request to Ollama format
    const ollamaRequestBody = {
      model: parsedBody.model,
      messages: parsedBody.messages.map(({ role, content }) => ({ role, content })),
      stream: parsedBody.stream,
    };

    const ollamaCloudUrl = process.env.OLLAMA_HOST || 'https://ollama.com';
    const apiKey = process.env.OLLAMA_API_KEY ||
                   'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    };

    const response = await fetch(`${ollamaCloudUrl}/api/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify(ollamaRequestBody),
    });

    if (!response.ok) {
      throw new Error(`Ollama Cloud returned ${response.status}: ${response.statusText}`);
    }

    // Check if response is streaming
    const contentType = response.headers.get('content-type');

    if (contentType?.includes('text/event-stream') || contentType?.includes('application/x-ndjson') || parsedBody.stream) {
      // Streaming response - proxy through
      const reader = response.body?.getReader();

      if (!reader) {
        throw new Error('No response body');
      }

      logger.info('[PROXY] Streaming chat response');

      // Set up streaming response (EXACT pattern from ollama-proxy.step.ts)
      return new Response(
        new ReadableStream({
          async start(controller) {
            try {
              while (true) {
                const { done, value } = await reader.read();

                if (done) {
                  controller.close();
                  break;
                }

                // Forward chunk as-is
                controller.enqueue(value);
              }
            } catch (error: any) {
              logger.error('Streaming error', { error: error.message });
              controller.error(error);
            }
          },
        }),
        {
          headers: {
            'Content-Type': contentType || 'application/x-ndjson',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
        }
      );
    } else {
      // Non-streaming response
      const data = await response.json();

      logger.info('[PROXY] Non-streaming chat response');

      return {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
        body: data,
      };
    }
  } catch (error: any) {
    logger.error('Ollama Chat Proxy error', { error: error.message });

    return {
      status: 500,
      body: { error: error.message },
    };
  }
};
