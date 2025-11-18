/**
 * Design Review Agent Step
 *
 * Architecture and design review using deepseek-v3.1:671b (671B parameters).
 * Analyzes system architecture, API design, scalability, and security.
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
  name: 'DesignReviewAgent',
  description: 'Architecture and design review using deepseek-v3.1:671b (671B parameters)',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/design-review/execute',
  emits: [],

  bodySchema: z.object({
    content: z.string().min(20, 'Design description must be at least 20 characters'),
    review_type: z.enum(['architecture', 'api', 'database', 'system']).default('architecture'),
    focus_areas: z.array(z.string()).optional().describe('Areas to focus on'),
    context: z.string().optional().describe('Additional context'),
  }),

  responseSchema: {
    200: z.object({
      content_hash: z.string(),
      review_type: z.string(),
      quality_score: z.number().min(0).max(100),
      issues_found: z.array(z.object({
        severity: z.enum(['critical', 'high', 'medium', 'low']),
        category: z.string().optional(),
        description: z.string(),
        suggestion: z.string().optional(),
      })),
      strengths: z.array(z.string()),
      recommendations: z.array(z.string()),
      overall_assessment: z.string(),
      scalability_analysis: z.string().optional(),
      security_considerations: z.array(z.string()).optional(),
      metadata: z.object({
        duration_ms: z.number(),
        model_used: z.string(),
      }).optional(),
    }),
    400: z.object({ error: z.string() }),
    500: z.object({ error: z.string(), details: z.any().optional() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { content, review_type, focus_areas, context } = req.body;

  logger.info('Design review agent starting', {
    review_type,
    contentLength: content.length,
  });

  const startTime = Date.now();

  try {
    // Generate content hash
    const crypto = require('crypto');
    const contentHash = crypto.createHash('md5').update(content).digest('hex');

    // Build comprehensive design review prompt
    const focusText = focus_areas && focus_areas.length > 0
      ? `\n\nPrioritize analysis of:\n${focus_areas.map(a => `- ${a}`).join('\n')}`
      : '';

    const contextText = context ? `\n\nAdditional context:\n${context}` : '';

    const prompt = `Perform a comprehensive ${review_type} design review:

${content}
${contextText}
${focusText}

As a senior architect, analyze:

1. **Architecture Quality** (0-100 score)
   - Design soundness and coherence
   - Component organization
   - Separation of concerns

2. **Scalability**
   - Horizontal/vertical scaling capability
   - Performance bottlenecks
   - Load handling strategy

3. **Security**
   - Security vulnerabilities
   - Authentication/authorization
   - Data protection

4. **Maintainability**
   - Code organization
   - Documentation quality
   - Technical debt risks

5. **Best Practices**
   - Industry standards adherence
   - Design patterns usage
   - Anti-patterns to avoid

Provide:
- Overall quality score (0-100)
- Critical/high/medium/low severity issues
- Design strengths
- Specific recommendations
- Scalability analysis
- Security considerations
- Overall assessment`;

    // Call Ollama Cloud (deepseek-v3.1:671b for deep reasoning)
    const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                         'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    logger.info('Calling deepseek-v3.1:671b for design review');

    const ollamaResponse = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'deepseek-v3.1:671b',
        prompt: prompt,
        system: 'You are a principal software architect. Provide deep, insightful design reviews considering scalability, security, maintainability, and long-term implications.',
        stream: false,
        options: {
          temperature: 0.5,
          num_predict: 3000,
        },
      }),
    });

    if (!ollamaResponse.ok) {
      logger.error('Ollama Cloud error', { status: ollamaResponse.status });

      // Fallback
      return {
        status: 200,
        body: {
          content_hash: contentHash,
          review_type,
          quality_score: 60,
          issues_found: [],
          strengths: ['Design review service unavailable'],
          recommendations: ['Retry when Ollama Cloud available'],
          overall_assessment: 'Fallback mode - full analysis unavailable',
          metadata: {
            duration_ms: Date.now() - startTime,
            model_used: 'fallback',
          },
        },
      };
    }

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    logger.info('Design review generated', { responseLength: responseText.length });

    // Parse quality score
    const scoreMatch = responseText.match(/(?:quality score|overall score):\s*(\d+)\/100/i) ||
                       responseText.match(/(\d+)\/100/);
    const qualityScore = scoreMatch ? parseInt(scoreMatch[1]) : 75;

    // Extract issues with severity
    const issues: any[] = [];
    const severityPatterns = [
      { pattern: /\[CRITICAL\]|Critical:/gi, severity: 'critical' },
      { pattern: /\[HIGH\]|High:/gi, severity: 'high' },
      { pattern: /\[MEDIUM\]|Medium:/gi, severity: 'medium' },
      { pattern: /\[LOW\]|Low:/gi, severity: 'low' },
    ];

    const lines = responseText.split('\n');
    let currentSeverity = 'medium';

    for (const line of lines) {
      const trimmed = line.trim();

      // Update severity context
      for (const { pattern, severity } of severityPatterns) {
        if (pattern.test(trimmed)) {
          currentSeverity = severity;
        }
      }

      // Extract issue from bullet point
      if ((trimmed.startsWith('-') || trimmed.startsWith('*')) && trimmed.length > 20) {
        const description = trimmed.replace(/^[-*]\s*/, '').replace(/\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*/i, '');
        if (description.toLowerCase().includes('issue') ||
            description.toLowerCase().includes('problem') ||
            description.toLowerCase().includes('concern') ||
            description.toLowerCase().includes('vulnerability')) {
          issues.push({
            severity: currentSeverity,
            category: review_type,
            description: description,
          });
        }
      }
    }

    // Extract strengths
    const strengths: string[] = [];
    let inStrengthsSection = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (/strengths?|positives?|good|well-designed/i.test(trimmed)) {
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
    let inRecSection = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (/recommendations?|improvements?|should consider/i.test(trimmed)) {
        inRecSection = true;
        continue;
      }

      if (/assessment|conclusion|summary/i.test(trimmed)) {
        inRecSection = false;
      }

      if (inRecSection && (trimmed.startsWith('-') || trimmed.startsWith('*') || /^\d+\./.test(trimmed))) {
        recommendations.push(trimmed.replace(/^[-*\d.]\s*/, ''));
      }
    }

    // Extract scalability analysis
    const scalabilityMatch = responseText.match(/scalability[:\s]+(.*?)(?:\n\n|security|recommendations?)/is);
    const scalabilityAnalysis = scalabilityMatch ? scalabilityMatch[1].trim().substring(0, 500) : undefined;

    // Extract security considerations
    const securityConsiderations: string[] = [];
    let inSecSection = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (/security|vulnerabilities?/i.test(trimmed)) {
        inSecSection = true;
        continue;
      }

      if (/scalability|maintainability|recommendations/i.test(trimmed)) {
        inSecSection = false;
      }

      if (inSecSection && (trimmed.startsWith('-') || trimmed.startsWith('*'))) {
        securityConsiderations.push(trimmed.replace(/^[-*]\s*/, ''));
      }
    }

    // Extract overall assessment
    const assessMatch = responseText.match(/(?:overall assessment|conclusion|summary)[:\s]+(.*?)$/is);
    const overallAssessment = assessMatch
      ? assessMatch[1].trim().substring(0, 500)
      : `Design review complete with quality score ${qualityScore}/100. ${issues.length} issues identified for improvement.`;

    const duration = Date.now() - startTime;

    const result = {
      content_hash: contentHash,
      review_type,
      quality_score: qualityScore,
      issues_found: issues.slice(0, 15),
      strengths: strengths.slice(0, 8),
      recommendations: recommendations.slice(0, 10),
      overall_assessment: overallAssessment,
      scalability_analysis: scalabilityAnalysis,
      security_considerations: securityConsiderations.slice(0, 8),
      metadata: {
        duration_ms: duration,
        model_used: 'deepseek-v3.1:671b',
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
          'design-review-agent',
          'VALIDATION',
          `${review_type} design review`,
          issues.length,
          recommendations.length,
          qualityScore / 100.0,
          duration,
        ]
      );
    } catch (e) {
      logger.warn('Audit logging failed', { error: (e as Error).message });
    }

    logger.info('Design review agent completed', {
      qualityScore,
      issuesFound: issues.length,
      recommendationsCount: recommendations.length,
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('Design review agent failed', {
      error: error.message,
      stack: error.stack,
    });

    return {
      status: 500,
      body: {
        error: 'Design review failed',
        details: {
          review_type,
          message: error.message,
        },
      },
    };
  }
};

/**
 * Example usage:
 *
 * POST /api/agents/design-review/execute
 *
 * {
 *   "content": "Microservices architecture with API gateway, 5 services, PostgreSQL, Redis, message queue...",
 *   "review_type": "architecture",
 *   "focus_areas": ["scalability", "security", "fault tolerance"]
 * }
 *
 * Response:
 * {
 *   "quality_score": 82,
 *   "issues_found": [
 *     {
 *       "severity": "high",
 *       "category": "architecture",
 *       "description": "Single point of failure in API gateway",
 *       "suggestion": "Implement redundant gateways with load balancing"
 *     }
 *   ],
 *   "strengths": [
 *     "Well-defined service boundaries",
 *     "Appropriate data store selections"
 *   ],
 *   "recommendations": [
 *     "Add circuit breakers for service resilience",
 *     "Implement distributed tracing"
 *   ],
 *   "scalability_analysis": "Architecture can scale horizontally...",
 *   "security_considerations": [
 *     "Implement API authentication at gateway",
 *     "Encrypt sensitive data at rest"
 *   ]
 * }
 */
