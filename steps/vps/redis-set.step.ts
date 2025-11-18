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
  name: 'RedisSet',
  description: 'Set value in Redis cache',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/redis/:key',
  emits: [],
  bodySchema: z.object({
    value: z.string(),
    ttl: z.number().optional(),
  }),
  responseSchema: {
    200: z.object({
      key: z.string(),
      value: z.string(),
      ttl: z.number().optional(),
    }),
    500: z.object({
      error: z.string(),
      message: z.string(),
    }),
  },
}

export const handler: Handlers['RedisSet'] = async (req: any, { logger }: any) => {
  const { key } = req.params as { key: string }
  const { value, ttl } = req.body

  try {
    logger.info('Redis SET attempt', { key, hasTtl: !!ttl, value })
    const client = await getRedisClient()
    logger.info('Redis client connected')

    if (ttl) {
      await client.setEx(key, ttl, value)
      logger.info('Redis SETEX success', { key, ttl })
    } else {
      await client.set(key, value)
      logger.info('Redis SET success', { key })
    }

    return {
      status: 200,
      body: { key, value, ttl },
    }
  } catch (error: any) {
    logger.error('Redis SET failed', { error: error.message, stack: error.stack })
    return {
      status: 500,
      body: {
        error: 'Redis operation failed',
        message: error.message,
      },
    }
  }
}
