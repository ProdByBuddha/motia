import { ApiRouteConfig, Handlers } from 'motia'
import { z } from 'zod'

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'HealthCheck',
  description: 'Health check endpoint for VPS orchestration service',
  flows: ['vps-orchestration'],
  method: 'GET',
  path: '/health',
  emits: [],
  responseSchema: {
    200: z.object({
      status: z.string(),
      service: z.string(),
      version: z.string(),
      timestamp: z.string(),
      integrations: z.object({
        postgres: z.string(),
        redis: z.string(),
        ollama: z.string(),
      }),
    }),
  },
}

export const handler: Handlers['HealthCheck'] = async (req: any, { logger }: any) => {
  logger.info('Health check requested')

  return {
    status: 200,
    body: {
      status: 'healthy',
      service: 'Motia VPS Orchestration',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
      integrations: {
        postgres: process.env.POSTGRES_HOST || 'not configured',
        redis: process.env.REDIS_HOST || 'not configured',
        ollama: process.env.OLLAMA_HOST || 'not configured',
      },
    },
  }
}
