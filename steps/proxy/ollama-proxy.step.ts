/**
 * Ollama Cloud Proxy for bolt.diy
 *
 * Proxies Ollama API requests from bolt.diy to Ollama Cloud with proper authentication.
 * Handles streaming responses in bolt.diy compatible format.
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'OllamaCloudProxy',
  description: 'Proxy Ollama API calls to Ollama Cloud with authentication',
  flows: ['proxy'],
  method: 'POST',
  path: '/api/ollama-proxy/api/*',
  emits: [],

  // Accept any body (proxying Ollama API format)
  bodySchema: z.any(),

  responseSchema: {
    200: z.any(),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  logger.info('Ollama Cloud Proxy handler invoked', { request: req });
  // Extract path from URL or originalUrl
  const fullPath = req.originalUrl || req.url || '';
  const path = fullPath.replace('/api/ollama-proxy/api/', '');

  logger.info('Ollama Cloud Proxy', { fullPath, path, body: req.body });

  try {
    const ollamaCloudUrl = process.env.OLLAMA_HOST || 'https://ollama.com';
    const apiKey = process.env.OLLAMA_API_KEY ||
                   'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    };

    logger.info('Forwarding to Ollama Cloud with headers:', { headers });

    // Forward request to Ollama Cloud with authentication
    const finalUrl = path ? `${ollamaCloudUrl}/api/${path}` : `${ollamaCloudUrl}/api/chat`;
    logger.info('Final URL:', { finalUrl });

    const response = await fetch(finalUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(req.body),
    });

    if (!response.ok) {
      throw new Error(`Ollama Cloud returned ${response.status}: ${response.statusText}`);
    }

    // Check if response is streaming
    const contentType = response.headers.get('content-type');

    if (contentType?.includes('text/event-stream') || contentType?.includes('application/x-ndjson')) {
      // Streaming response - proxy through
      const reader = response.body?.getReader();

      if (!reader) {
        throw new Error('No response body');
      }

      // Set up streaming response
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
            'Content-Type': contentType || 'application/json',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
        }
      );
    } else {
      // Non-streaming response
      const data = await response.json();

      return {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
        body: data,
      };
    }
  } catch (error: any) {
    logger.error('Ollama Cloud Proxy error', { error: error.message });

    return {
      status: 500,
      body: { error: error.message },
    };
  }
};

/**
 * Usage:
 *
 * From bolt.diy, instead of calling https://ollama.com/api/generate,
 * call: https://hq.iameternalzion.com/api/ollama-proxy/api/generate
 *
 * The proxy will:
 * 1. Add Bearer token authentication
 * 2. Forward request to Ollama Cloud
 * 3. Stream response back to bolt.diy
 * 4. Handle all auth/formatting
 */
