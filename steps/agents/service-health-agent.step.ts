/**
 * Service Health Agent
 *
 * Monitor all running services for availability, health, and dependencies.
 * Uses deepseek-v3.1:671b for service dependency analysis.
 */

import { z } from 'zod';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const config = {
  type: 'api',
  name: 'ServiceHealthAgent',
  description: 'Service availability and health monitoring',
  flows: ['vps-orchestration', 'infrastructure'],
  method: 'POST',
  path: '/api/agents/service-health/execute',
  emits: [],

  bodySchema: z.object({
    services: z.array(z.string()).optional().describe('Specific services to check'),
    include_docker: z.boolean().default(true),
    include_systemd: z.boolean().default(true),
  }),

  responseSchema: {
    200: z.object({
      services: z.array(z.object({
        service_name: z.string(),
        status: z.enum(['running', 'stopped', 'failed', 'degraded']),
        uptime: z.number().optional(),
        health_score: z.number(),
        issues: z.array(z.string()),
        dependencies: z.array(z.string()),
      })),
      summary: z.object({
        total_services: z.number(),
        running: z.number(),
        stopped: z.number(),
        failed: z.number(),
        degraded: z.number(),
      }),
      critical_issues: z.array(z.string()),
      recommendations: z.array(z.string()),
      metadata: z.object({
        duration_ms: z.number(),
        model_used: z.string(),
      }),
    }),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { services, include_docker, include_systemd } = req.body;

  logger.info('Service health agent starting');

  const startTime = Date.now();

  try {
    const serviceList: any[] = [];

    // Check Docker containers
    if (include_docker) {
      const dockerPs = await execAsync('docker ps -a --format "{{.Names}}|{{.Status}}|{{.State}}" 2>/dev/null || echo ""');

      for (const line of dockerPs.stdout.split('\n')) {
        if (line.trim()) {
          const [name, status, state] = line.split('|');
          serviceList.push({
            service_name: name,
            status: state === 'running' ? 'running' : state === 'exited' ? 'stopped' : 'degraded',
            uptime: 0,  // Would parse from status
            health_score: state === 'running' ? 100 : 0,
            issues: state !== 'running' ? [`Container ${state}`] : [],
            dependencies: [],
          });
        }
      }
    }

    // Check systemd services
    if (include_systemd) {
      const systemdServices = await execAsync('systemctl list-units --type=service --state=running,failed --no-pager --no-legend 2>/dev/null || echo ""');

      for (const line of systemdServices.stdout.split('\n').slice(0, 20)) {
        if (line.trim() && !line.includes('docker')) {  // Skip docker services (already checked)
          const parts = line.trim().split(/\s+/);
          if (parts.length >= 4) {
            const serviceName = parts[0].replace('.service', '');
            const loadState = parts[1];
            const activeState = parts[2];

            serviceList.push({
              service_name: serviceName,
              status: activeState === 'active' ? 'running' : activeState === 'failed' ? 'failed' : 'degraded',
              uptime: 0,
              health_score: activeState === 'active' ? 100 : activeState === 'failed' ? 0 : 50,
              issues: activeState !== 'active' ? [`Service ${activeState}`] : [],
              dependencies: [],
            });
          }
        }
      }
    }

    // Analyze with Ollama Cloud for dependency and health insights
    const prompt = `Analyze service health for VPS infrastructure:

Services Running:
${serviceList.map(s => `- ${s.service_name}: ${s.status}`).join('\n')}

Provide:
1. Critical issues requiring immediate attention
2. Service dependency relationships
3. Health optimization recommendations
4. Potential failure points

Focus on security and reliability implications.`;

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
        prompt,
        system: 'You are a site reliability engineer. Analyze service health and dependencies.',
        stream: false,
        options: { temperature: 0.4 },
      }),
    });

    if (!ollamaResponse.ok) {
      throw new Error('Service health analysis failed');
    }

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    // Extract critical issues
    const criticalIssues: string[] = [];
    const criticalMatches = responseText.matchAll(/(?:critical|urgent):?\s*([^\n]+)/gi);
    for (const match of criticalMatches) {
      criticalIssues.push(match[1].trim());
    }

    // Extract recommendations
    const recommendations: string[] = [];
    const recMatches = responseText.matchAll(/(?:recommend|suggest):?\s*([^\n]+)/gi);
    for (const match of recMatches) {
      recommendations.push(match[1].trim());
    }

    // Calculate summary
    const running = serviceList.filter(s => s.status === 'running').length;
    const stopped = serviceList.filter(s => s.status === 'stopped').length;
    const failed = serviceList.filter(s => s.status === 'failed').length;
    const degraded = serviceList.filter(s => s.status === 'degraded').length;

    const duration = Date.now() - startTime;

    const result = {
      services: serviceList,
      summary: {
        total_services: serviceList.length,
        running,
        stopped,
        failed,
        degraded,
      },
      critical_issues: criticalIssues.slice(0, 10),
      recommendations: recommendations.slice(0, 10),
      metadata: {
        duration_ms: duration,
        model_used: 'deepseek-v3.1:671b',
      },
    };

    logger.info('Service health check completed', {
      totalServices: serviceList.length,
      running,
      failed,
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('Service health agent failed', { error: error.message });

    return {
      status: 500,
      body: { error: 'Service health check failed' },
    };
  }
};
