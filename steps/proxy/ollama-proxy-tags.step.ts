/**
 * Ollama Cloud Proxy - /api/tags endpoint
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'OllamaProxyTags',
  description: 'Proxy /api/tags to Ollama Cloud',
  flows: ['proxy'],
  method: 'GET',
  path: '/api/ollama/api/tags',  // Match Bolt DIY's expected path
  emits: [],
  responseSchema: { 200: z.any(), 500: z.object({ error: z.string() }) },
};

export const handler = async (req: any, { logger }: any) => {
  try {
    const response = await fetch('https://ollama.com/api/tags', {
      headers: {
        'Authorization': 'Bearer c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g',
      },
    });

    const data = await response.json();
    return { status: 200, body: data };
  } catch (error: any) {
    return { status: 500, body: { error: error.message } };
  }
};
