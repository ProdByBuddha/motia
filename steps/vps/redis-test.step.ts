import { ApiRouteConfig, Handlers } from 'motia'
import { z } from 'zod'
import { createClient } from 'redis'

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'RedisTest',
  description: 'Test Redis connection',
  flows: ['vps-orchestration'],
  method: 'GET',
  path: '/api/redis-test',
  emits: [],
  responseSchema: {
    200: z.object({
      connected: z.boolean(),
      testValue: z.string().optional(),
    }),
    500: z.object({
      error: z.string(),
      message: z.string(),
    }),
  },
}

export const handler: Handlers['RedisTest'] = async (req: any, { logger }: any) => {
  let client

  try {
    logger.info('Redis test - creating client')

    client = createClient({
      socket: {
        host: process.env.REDIS_HOST || 'localhost',
        port: parseInt(process.env.REDIS_PORT || '6379'),
      },
      password: process.env.REDIS_PASSWORD,
    })

    logger.info('Redis test - connecting')
    await client.connect()

    logger.info('Redis test - connected, setting test value')
    await client.set('motia-test-key', 'Hello from Motia!')

    logger.info('Redis test - getting test value')
    const value = await client.get('motia-test-key')

    logger.info('Redis test - success', { value })

    await client.disconnect()

    return {
      status: 200,
      body: {
        connected: true,
        testValue: value || undefined,
      },
    }
  } catch (error: any) {
    logger.error('Redis test failed', { error: error.message, stack: error.stack })

    if (client) {
      try {
        await client.disconnect()
      } catch (e) {
        // Ignore disconnect errors
      }
    }

    return {
      status: 500,
      body: {
        error: 'Redis test failed',
        message: error.message,
      },
    }
  }
}
