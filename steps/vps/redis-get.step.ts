import { ApiRouteConfig, Handlers } from 'motia'
import { z } from 'zod'
import { createClient } from 'redis'

let redisClient: any = null

async function getRedisClient() {
  if (!redisClient) {
    redisClient = createClient({
      socket: {
        host: process.env.REDIS_HOST || 'localhost',
        port: parseInt(process.env.REDIS_PORT || '6379'),
      },
      password: process.env.REDIS_PASSWORD,
    })
    await redisClient.connect()
  }
  return redisClient
}

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'RedisGet',
  description: 'Get value from Redis cache',
  flows: ['vps-orchestration'],
  method: 'GET',
  path: '/api/redis/:key',
  emits: [],
  responseSchema: {
    200: z.object({
      key: z.string(),
      value: z.string().nullable(),
    }),
    500: z.object({
      error: z.string(),
      message: z.string(),
    }),
  },
}

export const handler: Handlers['RedisGet'] = async (req: any, { logger }: any) => {
  const { key } = req.params as { key: string }

  try {
    logger.info('Redis GET attempt', { key })
    const client = await getRedisClient()
    logger.info('Redis client connected')

    const value = await client.get(key)
    logger.info('Redis GET success', { key, hasValue: !!value })

    return {
      status: 200,
      body: { key, value },
    }
  } catch (error: any) {
    logger.error('Redis GET failed', { error: error.message, stack: error.stack })
    return {
      status: 500,
      body: {
        error: 'Redis operation failed',
        message: error.message,
      },
    }
  }
}
