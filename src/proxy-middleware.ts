/**
 * Ollama Cloud Streaming Proxy Middleware
 *
 * This bypasses Motia's subprocess step execution to enable real streaming.
 * Must be registered directly with Express before Motia's router.
 */

import express, { Request, Response } from 'express';

const OLLAMA_CLOUD_URL = process.env.OLLAMA_HOST || 'https://ollama.com';
const OLLAMA_API_KEY = process.env.OLLAMA_API_KEY ||
  'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

export function createOllamaStreamingProxy() {
  const router = express.Router();

  // Proxy /api/chat endpoint (streaming)
  router.post('/api/ollama/api/chat', async (req: Request, res: Response) => {
    try {
      console.log('[STREAMING-PROXY] Chat request:', {
        model: req.body.model,
        stream: req.body.stream
      });

      const response = await fetch(`${OLLAMA_CLOUD_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${OLLAMA_API_KEY}`,
        },
        body: JSON.stringify(req.body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[STREAMING-PROXY] Ollama Cloud error:', response.status, errorText);
        return res.status(response.status).json({ error: errorText });
      }

      // For non-streaming
      if (!req.body.stream) {
        const data = await response.json();
        return res.json(data);
      }

      // For streaming - pipe directly
      console.log('[STREAMING-PROXY] Starting stream');

      res.setHeader('Content-Type', response.headers.get('content-type') || 'application/x-ndjson');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');

      const reader = response.body?.getReader();
      if (!reader) {
        return res.status(500).json({ error: 'No response body' });
      }

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            res.end();
            break;
          }
          res.write(value);
        }
        console.log('[STREAMING-PROXY] Stream complete');
      } catch (error: any) {
        console.error('[STREAMING-PROXY] Stream error:', error.message);
        if (!res.headersSent) {
          res.status(500).json({ error: error.message });
        }
        res.end();
      }
    } catch (error: any) {
      console.error('[STREAMING-PROXY] Chat proxy error:', error.message);
      if (!res.headersSent) {
        res.status(500).json({ error: error.message });
      }
    }
  });

  // Proxy /api/generate endpoint (streaming)
  router.post('/api/ollama/api/generate', async (req: Request, res: Response) => {
    try {
      console.log('[STREAMING-PROXY] Generate request');

      const response = await fetch(`${OLLAMA_CLOUD_URL}/api/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${OLLAMA_API_KEY}`,
        },
        body: JSON.stringify(req.body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        return res.status(response.status).json({ error: errorText });
      }

      // For non-streaming
      if (!req.body.stream) {
        const data = await response.json();
        return res.json(data);
      }

      // For streaming - pipe directly
      res.setHeader('Content-Type', response.headers.get('content-type') || 'application/x-ndjson');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');

      const reader = response.body?.getReader();
      if (!reader) {
        return res.status(500).json({ error: 'No response body' });
      }

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            res.end();
            break;
          }
          res.write(value);
        }
      } catch (error: any) {
        console.error('[STREAMING-PROXY] Stream error:', error.message);
        res.end();
      }
    } catch (error: any) {
      console.error('[STREAMING-PROXY] Generate proxy error:', error.message);
      if (!res.headersSent) {
        res.status(500).json({ error: error.message });
      }
    }
  });

  return router;
}
