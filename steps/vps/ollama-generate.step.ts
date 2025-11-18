import { ApiRouteConfig, Handlers } from 'motia'
import { z } from 'zod'
import axios from 'axios'

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'OllamaGenerate',
  description: 'Generate text using Ollama LLM',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/ai/generate',
  emits: [],
  bodySchema: z.object({
    model: z.string().default('gpt-oss:20b'),
    prompt: z.string(),
    stream: z.boolean().default(false),
  }),
  responseSchema: {
    200: z.object({
      model: z.string(),
      response: z.string(),
      done: z.boolean(),
    }),
    400: z.object({
      error: z.string(),
    }),
    500: z.object({
      error: z.string(),
      message: z.string(),
    }),
  },
}

export const handler: Handlers['OllamaGenerate'] = async (req: any, { logger }: any) => {
  const defaultModel = process.env.OLLAMA_MODEL || 'llama2'
  const { model = defaultModel, prompt, stream = false } = req.body

  if (!prompt) {
    return {
      status: 400,
      body: { error: 'Prompt is required' },
    }
  }

  const ollamaHost = process.env.OLLAMA_HOST || 'http://localhost:11434'
  const url = `${ollamaHost}/api/generate`
  const requestBody = { model, prompt, stream }

  try {
    logger.info('Ollama request details', {
      url,
      model,
      promptLength: prompt.length,
      stream,
      ollamaHost
    })

    const response = await axios.post(url, requestBody)

    logger.info('Ollama response received', {
      status: response.status,
      hasResponse: !!response.data.response,
      done: response.data.done
    })

    return {
      status: 200,
      body: {
        model,
        response: response.data.response,
        done: response.data.done,
      },
    }
  } catch (error: any) {
    logger.error('Ollama generation failed', {
      error: error.message,
      status: error.response?.status,
      statusText: error.response?.statusText,
      responseData: error.response?.data,
      url,
      requestBody
    })
    return {
      status: 500,
      body: {
        error: 'Ollama generation failed',
        message: error.message,
      },
    }
  }
}
