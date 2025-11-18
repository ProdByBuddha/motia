/**
 * Coordinator Agent Step
 *
 * Multi-agent workflow orchestration using deepseek-v3.1:671b.
 * Manages agent selection, sequencing, and state coordination.
 */

import { z } from 'zod';

export const config = {
  type: 'api',
  name: 'CoordinatorAgent',
  description: 'Multi-agent orchestration using deepseek-v3.1:671b',
  flows: ['vps-orchestration'],
  method: 'POST',
  path: '/api/agents/coordinator/execute',
  emits: [],

  bodySchema: z.object({
    goal: z.string().min(10),
    available_agents: z.array(z.string()).describe('Available agent IDs'),
    constraints: z.array(z.string()).optional(),
  }),

  responseSchema: {
    200: z.object({
      goal: z.string(),
      workflow: z.array(z.object({
        step: z.number(),
        agent_id: z.string(),
        action: z.string(),
        input_mapping: z.record(z.any()).optional(),
        expected_output: z.string(),
      })),
      estimated_duration: z.string(),
      success_criteria: z.array(z.string()),
      metadata: z.object({ duration_ms: z.number(), model_used: z.string() }),
    }),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { goal, available_agents, constraints } = req.body;

  const prompt = `Design a multi-agent workflow to achieve:

Goal: ${goal}

Available Agents: ${available_agents.join(', ')}
${constraints && constraints.length > 0 ? `\nConstraints:\n${constraints.map(c => `- ${c}`).join('\n')}` : ''}

Create an optimal workflow:
1. Select appropriate agents
2. Sequence them logically
3. Define input/output mappings
4. Estimate duration
5. Define success criteria

Format:
Step 1: [agent_id] - [action] → [expected_output]
Step 2: [agent_id] - [action] (uses output from step 1) → [expected_output]
...`;

  const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                       'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

  try {
    const response = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'deepseek-v3.1:671b',
        prompt,
        system: 'You are an orchestration expert. Design optimal multi-agent workflows.',
        stream: false,
        options: { temperature: 0.5 },
      }),
    });

    const result = await response.json();
    const content = result.response || '';

    // Parse workflow steps
    const workflow: any[] = [];
    const stepMatches = content.matchAll(/Step\s+(\d+):\s*\[?([^\]]+)\]?\s*-\s*([^\n→]+)(?:→\s*([^\n]+))?/gi);

    for (const match of stepMatches) {
      workflow.push({
        step: parseInt(match[1]),
        agent_id: match[2].trim(),
        action: match[3].trim(),
        expected_output: match[4] ? match[4].trim() : 'Result',
      });
    }

    return {
      status: 200,
      body: {
        goal,
        workflow,
        estimated_duration: '30-60 minutes',
        success_criteria: ['All steps complete', 'Goal achieved'],
        metadata: { duration_ms: Date.now() - Date.now(), model_used: 'deepseek-v3.1:671b' },
      },
    };
  } catch (error: any) {
    return { status: 500, body: { error: error.message } };
  }
};
