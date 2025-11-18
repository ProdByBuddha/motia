/**
 * Research Agent Step
 *
 * Implements deep research capability as a Motia orchestration step
 * Coordinates with Tavily/WebSearch for comprehensive investigation
 */

import { z } from 'zod';
import { createClient } from 'redis';

let redisClient: any = null;

async function getRedisClient() {
  if (!redisClient) {
    redisClient = createClient({
      socket: {
        host: process.env.REDIS_HOST || 'redis',
        port: parseInt(process.env.REDIS_PORT || '6379'),
      },
      password: process.env.REDIS_PASSWORD,
    });
    await redisClient.connect();
  }
  return redisClient;
}

export const config = {
  type: 'api',
  name: 'ResearchAgent',
  description: 'Comprehensive research workflow using deep investigation patterns',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/research/execute',
  emits: [],

  bodySchema: z.object({
    query: z.string().min(5, 'Query must be at least 5 characters'),
    depth: z.enum(['quick', 'standard', 'deep']).default('standard').describe('Research depth'),
    maxHops: z.number().int().min(1).max(5).default(3).describe('Maximum search hops'),
    domain: z.string().optional().describe('Restrict to domain'),
  }),

  responseSchema: {
    200: z.object({
      query: z.string(),
      findings: z.array(z.string()).describe('Key findings'),
      sources: z.array(z.object({
        url: z.string(),
        title: z.string(),
        relevance: z.number().min(0).max(1),
      })),
      confidence: z.number().min(0).max(1).describe('Confidence in findings'),
      metadata: z.object({
        totalSources: z.number(),
        hopsUsed: z.number(),
        duration: z.number(),
      }),
    }),
    400: z.object({ error: z.string() }),
    500: z.object({ error: z.string(), details: z.any().optional() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { query, depth, maxHops, domain } = req.body;

  logger.info('Research agent starting', {
    query,
    depth,
    maxHops,
  });

  const startTime = Date.now();

  try {
    // Mock research result - in production would call SuperQwen + Tavily
    const redis = await getRedisClient();

    // Check cache for recent research on same query
    const cacheKey = `research:${query}:${depth}`;
    let cached = null;
    try {
      cached = await redis.get(cacheKey);
      if (cached) cached = JSON.parse(cached);
    } catch (e) {
      // Cache miss or parse error, continue
    }

    if (cached) {
      logger.info('Research cache hit', { cacheKey });
      return {
        status: 200,
        body: cached,
      };
    }

    // Mock research result for Phase 1 demo
    // In production: await superqwen.execute('research-agent', {...})
    const researchResult = {
      findings: [
        'AI orchestration platforms coordinate multiple AI agents and tools',
        'Key benefits include improved reliability and scalability',
        'Popular platforms: Motia, AutoGPT, CrewAI, LangChain',
      ],
      sources: [
        { url: 'https://github.com/motiadev/motia', title: 'Motia Framework', relevance: 0.9 },
        { url: 'https://crewai.com', title: 'CrewAI', relevance: 0.8 },
      ],
      confidence: 0.85,
      hopsUsed: depth === 'quick' ? 1 : depth === 'standard' ? 2 : 3,
    };

    // Validate and transform result
    const output = {
      query,
      findings: researchResult.findings || [],
      sources: (researchResult.sources || []).map((src: any) => ({
        url: src.url,
        title: src.title,
        relevance: src.relevance || 0.5,
      })),
      confidence: researchResult.confidence || 0.7,
      metadata: {
        totalSources: (researchResult.sources || []).length,
        hopsUsed: researchResult.hopsUsed || 1,
        duration: Date.now() - startTime,
      },
    };

    // Cache successful result (24 hours)
    try {
      await redis.setEx(cacheKey, 86400, JSON.stringify(output));
    } catch (e) {
      logger.warn('Failed to cache research result', { error: (e as any).message });
    }

    logger.info('Research agent completed', {
      findingCount: output.findings.length,
      sourceCount: output.sources.length,
      confidence: output.confidence,
      duration: output.metadata.duration,
    });

    return {
      status: 200,
      body: output,
    };

  } catch (error: any) {
    logger.error('Research agent failed', {
      error: error.message,
      stack: error.stack,
      query,
    });

    return {
      status: 500,
      body: {
        error: 'Research execution failed',
        details: {
          query,
          depth,
          message: error.message,
        },
      },
    };
  }
};

/**
 * Example usage in workflow:
 *
 * {
 *   id: 'research-step',
 *   agentId: 'research-agent',
 *   input: {
 *     query: '{{ params.topic }}',
 *     depth: 'deep',
 *     maxHops: 4,
 *   },
 * }
 */
