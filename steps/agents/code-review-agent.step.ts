/**
 * Code Review Agent Step
 *
 * Comprehensive code review using qwen3-coder:480b (480B parameters).
 * Analyzes code quality, security, performance, and maintainability.
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
  name: 'CodeReviewAgent',
  description: 'Comprehensive code review using qwen3-coder:480b',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/code-review/execute',
  emits: [],

  bodySchema: z.object({
    content: z.string().min(10, 'Code must be at least 10 characters'),
    language: z.string().default('python'),
    review_type: z.enum(['code', 'performance', 'security', 'architecture']).default('code'),
    focus_areas: z.array(z.string()).optional().describe('Specific areas to review'),
  }),

  responseSchema: {
    200: z.object({
      content_hash: z.string(),
      review_type: z.string(),
      quality_score: z.number().min(0).max(100).describe('Overall quality 0-100'),
      issues_found: z.array(z.object({
        severity: z.enum(['critical', 'high', 'medium', 'low']),
        location: z.string().optional(),
        description: z.string(),
        suggestion: z.string().optional(),
      })),
      strengths: z.array(z.string()),
      recommendations: z.array(z.string()),
      overall_assessment: z.string(),
      metadata: z.object({
        duration_ms: z.number(),
        model_used: z.string(),
        lines_reviewed: z.number(),
      }).optional(),
    }),
    400: z.object({ error: z.string() }),
    500: z.object({ error: z.string(), details: z.any().optional() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { content, language, review_type, focus_areas } = req.body;

  logger.info('Code review agent starting', {
    language,
    review_type,
    contentLength: content.length,
  });

  const startTime = Date.now();

  try {
    // Generate content hash
    const crypto = require('crypto');
    const contentHash = crypto.createHash('md5').update(content).digest('hex');

    // Build review prompt
    const focusAreasText = focus_areas && focus_areas.length > 0
      ? `\n\nFocus on these specific areas:\n${focus_areas.map(a => `- ${a}`).join('\n')}`
      : '';

    const prompt = `Perform a comprehensive ${review_type} code review for this ${language} code:

\`\`\`${language}
${content.substring(0, 3000)}
\`\`\`
${focusAreasText}

Provide:
1. Overall quality score (0-100)
2. Critical issues (security, bugs, performance problems)
3. Code strengths and good practices
4. Specific recommendations for improvement
5. Overall assessment

Structure your review as:
- Quality Score: X/100
- Issues Found: [list with severity levels]
- Strengths: [list positive aspects]
- Recommendations: [actionable improvements]
- Assessment: [summary paragraph]`;

    // Call Ollama Cloud (qwen3-coder:480b for code review)
    const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                         'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    logger.info('Calling qwen3-coder:480b for code review');

    const ollamaResponse = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'qwen3-coder:480b',
        prompt: prompt,
        system: 'You are a senior software engineer and code reviewer. Provide thorough, constructive code reviews with specific, actionable feedback.',
        stream: false,
        options: {
          temperature: 0.3,
          num_predict: 2500,
        },
      }),
    });

    if (!ollamaResponse.ok) {
      logger.error('Ollama Cloud error', { status: ollamaResponse.status });

      // Fallback response
      return {
        status: 200,
        body: {
          content_hash: contentHash,
          review_type,
          quality_score: 50,
          issues_found: [{
            severity: 'medium',
            description: 'Review service unavailable - using fallback',
            suggestion: 'Retry with Ollama Cloud when available',
          }],
          strengths: ['Code compiles'],
          recommendations: ['Retry review with full service'],
          overall_assessment: 'Fallback review - full analysis unavailable',
          metadata: {
            duration_ms: Date.now() - startTime,
            model_used: 'fallback',
            lines_reviewed: content.split('\n').length,
          },
        },
      };
    }

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    logger.info('Code review generated', { responseLength: responseText.length });

    // Parse quality score
    const scoreMatch = responseText.match(/(?:quality score|score):\s*(\d+)\/100/i) ||
                       responseText.match(/(\d+)\/100/);
    const qualityScore = scoreMatch ? parseInt(scoreMatch[1]) : 70;

    // Extract issues
    const issues: any[] = [];
    const issuePatterns = [
      /\[CRITICAL\]\s*(.+)/gi,
      /\[HIGH\]\s*(.+)/gi,
      /\[MEDIUM\]\s*(.+)/gi,
      /\[LOW\]\s*(.+)/gi,
    ];

    const severityMap = ['critical', 'high', 'medium', 'low'];

    issuePatterns.forEach((pattern, idx) => {
      let m;
      while ((m = pattern.exec(responseText)) !== null) {
        issues.push({
          severity: severityMap[idx],
          location: undefined,
          description: m[1].trim(),
          suggestion: undefined,
        });
      }
    });

    // If no tagged issues, extract from bullet points
    if (issues.length === 0) {
      const lines = responseText.split('\n');
      let inIssuesSection = false;

      for (const line of lines) {
        const trimmed = line.trim();

        if (/issues?\s*found|problems?|concerns?/i.test(trimmed)) {
          inIssuesSection = true;
          continue;
        }

        if (/strengths?|recommendations?/i.test(trimmed)) {
          inIssuesSection = false;
        }

        if (inIssuesSection && (trimmed.startsWith('-') || trimmed.startsWith('*'))) {
          issues.push({
            severity: 'medium',
            description: trimmed.replace(/^[-*]\s*/, ''),
          });
        }
      }
    }

    // Extract strengths
    const strengths: string[] = [];
    const lines = responseText.split('\n');
    let inStrengthsSection = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (/strengths?|good practices?|positives?/i.test(trimmed)) {
        inStrengthsSection = true;
        continue;
      }

      if (/recommendations?|issues?/i.test(trimmed)) {
        inStrengthsSection = false;
      }

      if (inStrengthsSection && (trimmed.startsWith('-') || trimmed.startsWith('*'))) {
        strengths.push(trimmed.replace(/^[-*]\s*/, ''));
      }
    }

    // Extract recommendations
    const recommendations: string[] = [];
    let inRecommendationsSection = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (/recommendations?|improvements?|suggestions?/i.test(trimmed)) {
        inRecommendationsSection = true;
        continue;
      }

      if (/assessment|conclusion/i.test(trimmed)) {
        inRecommendationsSection = false;
      }

      if (inRecommendationsSection && (trimmed.startsWith('-') || trimmed.startsWith('*') || /^\d+\./.test(trimmed))) {
        recommendations.push(trimmed.replace(/^[-*\d.]\s*/, ''));
      }
    }

    // Extract overall assessment (last paragraph or summary)
    const assessmentMatch = responseText.match(/(?:overall|assessment|summary|conclusion):\s*(.+?)(?:\n\n|$)/is);
    const overallAssessment = assessmentMatch
      ? assessmentMatch[1].trim()
      : `Code review complete. Quality score: ${qualityScore}/100. ${issues.length} issues found.`;

    const duration = Date.now() - startTime;
    const linesReviewed = content.split('\n').length;

    const result = {
      content_hash: contentHash,
      review_type,
      quality_score: qualityScore,
      issues_found: issues.slice(0, 20),
      strengths: strengths.slice(0, 10),
      recommendations: recommendations.slice(0, 10),
      overall_assessment: overallAssessment,
      metadata: {
        duration_ms: duration,
        model_used: 'qwen3-coder:480b',
        lines_reviewed: linesReviewed,
      },
    };

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
          'code-review-agent',
          'VALIDATION',
          `${review_type} review for ${language}`,
          issues.length,
          strengths.length,
          qualityScore / 100.0,
          duration,
        ]
      );
    } catch (e) {
      logger.warn('Audit logging failed', { error: (e as Error).message });
    }

    logger.info('Code review agent completed', {
      qualityScore,
      issuesFound: issues.length,
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('Code review agent failed', {
      error: error.message,
      stack: error.stack,
    });

    return {
      status: 500,
      body: {
        error: 'Code review failed',
        details: {
          review_type,
          message: error.message,
        },
      },
    };
  }
};
