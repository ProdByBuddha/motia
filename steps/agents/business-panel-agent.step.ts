/**
 * Business Panel Agent Step
 *
 * Multi-expert strategic analysis using deepseek-v3.1:671b (671B parameters).
 * Synthesizes insights from 9 business thought leaders.
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'BusinessPanelAgent',
  description: 'Multi-expert business analysis using deepseek-v3.1:671b',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/business-panel/execute',
  emits: [],

  bodySchema: z.object({
    subject: z.string().min(20),
    analysis_type: z.enum(['strategic', 'competitive', 'innovation', 'risk']).default('strategic'),
    experts: z.array(z.string()).optional().describe('Specific experts to consult'),
  }),

  responseSchema: {
    200: z.object({
      subject: z.string(),
      analysis_type: z.string(),
      expert_insights: z.array(z.object({
        expert: z.string(),
        framework: z.string(),
        analysis: z.string(),
      })),
      synthesis: z.string(),
      recommendations: z.array(z.string()),
      confidence: z.number(),
      metadata: z.object({
        duration_ms: z.number(),
        model_used: z.string(),
      }).optional(),
    }),
    400: z.object({ error: z.string() }),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { subject, analysis_type, experts } = req.body;

  logger.info('Business panel agent starting', { subject: subject.substring(0, 50), analysis_type });

  const startTime = Date.now();

  try {
    const expertList = experts || ['Porter', 'Christensen', 'Drucker', 'Collins', 'Taleb'];

    const prompt = `Provide multi-expert business analysis from the perspective of these thought leaders:
${expertList.join(', ')}

Subject: ${subject}
Analysis Type: ${analysis_type}

For each expert, provide their unique perspective and framework-based analysis. Then synthesize insights.

Format:
**EXPERT NAME (Framework)**: Analysis from their perspective
...
**SYNTHESIS**: Integrated insights
**RECOMMENDATIONS**: Strategic recommendations`;

    const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                         'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    const ollamaResponse = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'deepseek-v3.1:671b',
        prompt: prompt,
        system: 'You are a panel of business experts. Provide multi-perspective strategic analysis.',
        stream: false,
        options: { temperature: 0.7, num_predict: 3000 },
      }),
    });

    if (!ollamaResponse.ok) throw new Error('Business panel analysis failed');

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    // Parse expert insights
    const expertInsights: any[] = [];
    const expertMatches = responseText.matchAll(/\*\*([A-Z]+(?:\s+[A-Z]+)?)\s*\(([^)]+)\)\*\*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)/g);

    for (const match of expertMatches) {
      expertInsights.push({
        expert: match[1],
        framework: match[2],
        analysis: match[3].trim(),
      });
    }

    // Extract synthesis
    const synthesisMatch = responseText.match(/\*\*SYNTHESIS\*\*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)/i);
    const synthesis = synthesisMatch ? synthesisMatch[1].trim() : 'Multi-expert analysis complete.';

    // Extract recommendations
    const recommendations: string[] = [];
    const recMatch = responseText.match(/\*\*RECOMMENDATIONS?\*\*:\s*([\s\S]+?)$/i);

    if (recMatch) {
      const recLines = recMatch[1].split('\n');
      for (const line of recLines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('-') || trimmed.startsWith('*') || /^\d+\./.test(trimmed)) {
          recommendations.push(trimmed.replace(/^[-*\d.]\s*/, ''));
        }
      }
    }

    const duration = Date.now() - startTime;

    return {
      status: 200,
      body: {
        subject,
        analysis_type,
        expert_insights: expertInsights,
        synthesis,
        recommendations: recommendations.slice(0, 8),
        confidence: 0.85,
        metadata: {
          duration_ms: duration,
          model_used: 'deepseek-v3.1:671b',
        },
      },
    };

  } catch (error: any) {
    logger.error('Business panel failed', { error: error.message });

    return {
      status: 500,
      body: { error: 'Business panel analysis failed' },
    };
  }
};
