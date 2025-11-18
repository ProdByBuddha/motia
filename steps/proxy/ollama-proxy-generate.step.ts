/**
 * Ollama Cloud Proxy - /api/generate endpoint
 * Uses exact same pattern as ollama-proxy.step.ts (which works)
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'OllamaProxyGenerate',
  description: 'Proxy /api/generate to Ollama Cloud',
  flows: ['proxy'],
  method: 'POST',
  path: '/api/ollama/api/generate',
  emits: [],
  bodySchema: z.any(),
  responseSchema: { 200: z.any(), 500: z.object({ error: z.string() }) },
};

export const handler = async (req: any, { logger }: any) => {
  logger.info('Ollama Generate Proxy - Processing request');

  try {
    const ollamaCloudUrl = process.env.OLLAMA_HOST || 'https://ollama.com';
    const apiKey = process.env.OLLAMA_API_KEY ||
                   'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    };

    logger.info('[PROXY] Proxying generate to Ollama Cloud');

    const response = await fetch(`${ollamaCloudUrl}/api/generate`, {
      method: 'POST',
      headers,
      body: JSON.stringify(req.body),
    });

    if (!response.ok) {
      throw new Error(`Ollama Cloud returned ${response.status}: ${response.statusText}`);
    }

    // Check if response is streaming
    const contentType = response.headers.get('content-type');

    if (contentType?.includes('text/event-stream') || contentType?.includes('application/x-ndjson') || req.body.stream) {
      // Streaming response - proxy through
      const reader = response.body?.getReader();

      if (!reader) {
        throw new Error('No response body');
      }

      logger.info('[PROXY] Streaming generate response');

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

      logger.info('[PROXY] Non-streaming generate response');

      return {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
        body: data,
      };
    }
  } catch (error: any) {
    logger.error('Ollama Generate Proxy error', { error: error.message });

    return {
      status: 500,
      body: { error: error.message },
    };
  }
};
