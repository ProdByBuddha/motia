/**
 * Documentation Agent Step
 *
 * Auto-generate comprehensive documentation using gpt-oss:120b model.
 * Creates API docs, guides, architecture docs, and more.
 */

import { z } from 'zod';
import { createClient } from 'redis';
import { Pool } from 'pg';

let redisClient: any = null;
let pgPool: any = null;

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

function getPgPool() {
  if (!pgPool) {
    pgPool = new Pool({
      host: process.env.POSTGRES_HOST || 'postgres',
      port: parseInt(process.env.POSTGRES_PORT || '5432'),
      database: process.env.POSTGRES_DB || 'billionmail',
      user: process.env.POSTGRES_USER || 'postgres',
      password: process.env.POSTGRES_PASSWORD || 'postgres',
    });
  }
  return pgPool;
}

export const config = {
  type: 'api',
  name: 'DocumentationAgent',
  description: 'Generate comprehensive documentation using gpt-oss:120b model',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/documentation/execute',
  emits: [],

  bodySchema: z.object({
    subject: z.string().min(10, 'Subject must be at least 10 characters'),
    doc_type: z.enum(['api', 'guide', 'architecture', 'tutorial', 'reference']).default('api'),
    audience: z.string().default('developer').describe('Target audience'),
    include_examples: z.boolean().default(true).describe('Include code examples'),
    code_context: z.string().optional().describe('Code to document'),
  }),

  responseSchema: {
    200: z.object({
      subject: z.string(),
      doc_type: z.string(),
      title: z.string(),
      sections: z.array(z.object({
        title: z.string(),
        content: z.string(),
        level: z.number().min(1).max(6),
        examples: z.array(z.string()).optional(),
      })),
      table_of_contents: z.array(z.string()),
      metadata: z.object({
        duration_ms: z.number(),
        cached: z.boolean(),
        model_used: z.string(),
        word_count: z.number(),
      }).optional(),
    }),
    400: z.object({ error: z.string() }),
    500: z.object({ error: z.string(), details: z.any().optional() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { subject, doc_type, audience, include_examples, code_context } = req.body;

  logger.info('Documentation agent starting', {
    subject: subject.substring(0, 50),
    doc_type,
    audience,
  });

  const startTime = Date.now();

  try {
    const redis = await getRedisClient();

    // Cache key
    const cacheKey = `doc-gen:${Buffer.from(`${subject}:${doc_type}:${audience}`).toString('base64')}`;

    // Check cache (1-hour TTL)
    let cached = null;
    try {
      const cachedData = await redis.get(cacheKey);
      if (cachedData) {
        cached = JSON.parse(cachedData);
        logger.info('Documentation cache hit', { cacheKey });

        return {
          status: 200,
          body: {
            ...cached,
            metadata: {
              ...cached.metadata,
              cached: true,
            },
          },
        };
      }
    } catch (e) {
      logger.warn('Cache retrieval failed', { error: (e as Error).message });
    }

    // Build documentation prompt
    const prompt = `Generate comprehensive ${doc_type} documentation for:

Subject: ${subject}

Target Audience: ${audience}

${code_context ? `Code to document:\n\`\`\`\n${code_context.substring(0, 1000)}\n\`\`\`\n` : ''}

Create documentation with:
1. Clear title
2. Overview/introduction
3. Main sections with detailed content
4. ${include_examples ? 'Code examples where relevant' : 'Explanations without code'}
5. Table of contents
6. ${doc_type === 'api' ? 'API endpoints with parameters and responses' : ''}
${doc_type === 'tutorial' ? 'Step-by-step instructions' : ''}

Format as structured markdown with clear headings.`;

    // Call Ollama Cloud (gpt-oss:120b for documentation)
    const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                         'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    logger.info('Calling Ollama Cloud with gpt-oss:120b for documentation');

    const ollamaResponse = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gpt-oss:120b',
        prompt: prompt,
        system: 'You are a technical writer. Create clear, comprehensive documentation with good structure and examples.',
        stream: false,
        options: {
          temperature: 0.5,
          num_predict: 3000,
        },
      }),
    });

    if (!ollamaResponse.ok) {
      logger.error('Ollama Cloud API error', { status: ollamaResponse.status });

      // Fallback to template
      return {
        status: 200,
        body: {
          subject,
          doc_type,
          title: `${subject} Documentation`,
          sections: [
            {
              title: 'Overview',
              content: `Documentation for ${subject}. This is a fallback template.`,
              level: 1,
              examples: [],
            },
          ],
          table_of_contents: ['Overview'],
          metadata: {
            duration_ms: Date.now() - startTime,
            cached: false,
            model_used: 'fallback',
            word_count: 10,
          },
        },
      };
    }

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    logger.info('Documentation generated', { responseLength: responseText.length });

    // Parse sections from response (extract headings)
    const sections: any[] = [];
    const lines = responseText.split('\n');
    let currentSection: any = null;

    for (const line of lines) {
      // Detect markdown headings
      const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);

      if (headingMatch) {
        // Save previous section
        if (currentSection) {
          sections.push(currentSection);
        }

        // Start new section
        currentSection = {
          title: headingMatch[2].trim(),
          content: '',
          level: headingMatch[1].length,
          examples: [],
        };
      } else if (currentSection) {
        // Add content to current section
        currentSection.content += line + '\n';

        // Extract code examples
        if (line.includes('```') && include_examples) {
          const codeMatch = line.match(/```(\w+)?/);
          if (codeMatch && currentSection.examples) {
            currentSection.examples.push(line);
          }
        }
      }
    }

    // Add final section
    if (currentSection) {
      sections.push(currentSection);
    }

    // Generate table of contents
    const toc = sections.map(s => `${'  '.repeat(s.level - 1)}- ${s.title}`);

    // Extract title (first h1 or use subject)
    const titleSection = sections.find(s => s.level === 1);
    const title = titleSection ? titleSection.title : `${subject} Documentation`;

    // Count words
    const wordCount = responseText.split(/\s+/).length;

    const duration = Date.now() - startTime;

    const result = {
      subject,
      doc_type,
      title,
      sections: sections.map(s => ({
        title: s.title,
        content: s.content.trim(),
        level: s.level,
        examples: s.examples || [],
      })),
      table_of_contents: toc,
      metadata: {
        duration_ms: duration,
        cached: false,
        model_used: 'gpt-oss:120b',
        word_count: wordCount,
      },
    };

    // Cache (1-hour TTL)
    try {
      await redis.setEx(cacheKey, 3600, JSON.stringify(result));
    } catch (e) {
      logger.warn('Failed to cache', { error: (e as Error).message });
    }

    // Log to audit
    const postgres = getPgPool();
    try {
      await postgres.query(
        `INSERT INTO agent_executions (
          agent_id, capability, query, findings_count,
          sources_count, confidence, duration_ms, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())`,
        [
          'documentation-agent',
          'GENERATION',
          subject,
          sections.length,
          wordCount,
          1.0,
          duration,
        ]
      );
    } catch (e) {
      logger.warn('Audit logging failed', { error: (e as Error).message });
    }

    logger.info('Documentation agent completed', {
      sections: sections.length,
      wordCount,
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('Documentation agent failed', {
      error: error.message,
      stack: error.stack,
    });

    return {
      status: 500,
      body: {
        error: 'Documentation generation failed',
        details: {
          subject,
          message: error.message,
        },
      },
    };
  }
};
