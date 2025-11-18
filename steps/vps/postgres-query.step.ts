import { ApiRouteConfig, Handlers } from 'motia'
import { z } from 'zod'
import { Client } from 'pg'

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'PostgresQuery',
  description: 'Execute PostgreSQL queries against BillionMail database',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/postgres/query',
  emits: [],
  bodySchema: z.object({
    query: z.string(),
    params: z.array(z.any()).optional(),
  }),
  responseSchema: {
    200: z.object({
      rows: z.array(z.any()),
      rowCount: z.number(),
      fields: z.array(z.string()),
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

export const handler: Handlers['PostgresQuery'] = async (req: any, { logger }: any) => {
  const { query, params = [] } = req.body

  if (!query) {
    return {
      status: 400,
      body: { error: 'Query is required' },
    }
  }

  const client = new Client({
    host: process.env.POSTGRES_HOST,
    port: parseInt(process.env.POSTGRES_PORT || '5432'),
    user: process.env.POSTGRES_USER,
    password: process.env.POSTGRES_PASSWORD,
    database: process.env.POSTGRES_DB,
  })

  try {
    await client.connect()
    logger.info('Executing PostgreSQL query', { query, paramsCount: params.length })

    const result = await client.query(query, params)

    return {
      status: 200,
      body: {
        rows: result.rows,
        rowCount: result.rowCount || 0,
        fields: result.fields.map(f => f.name),
      },
    }
  } catch (error: any) {
    logger.error('PostgreSQL query failed', { error: error.message })
    return {
      status: 500,
      body: {
        error: 'Database query failed',
        message: error.message,
      },
    }
  } finally {
    await client.end()
  }
}
