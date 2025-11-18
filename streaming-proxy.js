const express = require('express');
const fetch = require('node-fetch');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

const OLLAMA_CLOUD_URL = process.env.OLLAMA_HOST || 'https://ollama.com';
const OLLAMA_API_KEY = process.env.OLLAMA_API_KEY;
const PORT = process.env.STREAMING_PROXY_PORT || 3001;

const handleOllamaRequest = async (req, res, endpoint) => {
  console.log(`[STREAM-PROXY] ${endpoint} request - model: ${req.body.model} stream: ${!!req.body.stream}`);

  try {
    const { think, ...ollamaBody } = req.body;

    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${OLLAMA_API_KEY}`,
    };

    const response = await fetch(`${OLLAMA_CLOUD_URL}/api/${endpoint}`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(ollamaBody),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[STREAM-PROXY] Ollama API error: ${response.status} ${response.statusText}`, errorText);
      return res.status(response.status).send(errorText);
    }

    // Correctly handle streaming vs. non-streaming
    if (ollamaBody.stream) {
      console.log('[STREAM-PROXY] Streaming response - direct passthrough');
      res.setHeader('Content-Type', 'text/event-stream'); res.setHeader('Connection', 'keep-alive'); res.setHeader('Cache-Control', 'no-cache');
      response.body.pipe(res);
    } else {
      console.log('[STREAM-PROXY] Non-streaming response - sending as JSON');
      const data = await response.json();
      res.json(data);
    }
  } catch (error) {
    console.error('[STREAM-PROXY] Error:', error.message);
    res.status(500).json({ error: 'Internal Server Error' });
  }
};

app.post('/api/chat', (req, res) => handleOllamaRequest(req, res, 'chat'));
app.post('/api/generate', (req, res) => handleOllamaRequest(req, res, 'generate'));

app.get('/api/tags', async (req, res) => {
    try {
        const response = await fetch(`${OLLAMA_CLOUD_URL}/api/tags`, {
            headers: { Authorization: `Bearer ${OLLAMA_API_KEY}` }
        });
        if (!response.ok) {
            throw new Error(`Ollama API error: ${response.status}`);
        }
        const data = await response.json();
        res.json(data);
    } catch (error) {
        console.error('[STREAM-PROXY] Error fetching tags:', error.message);
        res.status(500).json({ error: 'Failed to fetch tags' });
    }
});


app.listen(PORT, () => {
  console.log(`🚀 Ollama Streaming Proxy ready on port ${PORT}`);
  console.log(`   - Chat: http://localhost:${PORT}/api/chat`);
  console.log(`   - Generate: http://localhost:${PORT}/api/generate`);
  console.log(`   - Tags: http://localhost:${PORT}/api/tags`);
});