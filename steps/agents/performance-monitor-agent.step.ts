/**
 * Performance Monitor Agent
 *
 * Real-time system performance monitoring and optimization recommendations.
 * Uses deepseek-v3.1:671b for performance pattern analysis.
 */

import { z } from 'zod';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const config = {
  type: 'api',
  name: 'PerformanceMonitorAgent',
  description: 'Real-time performance monitoring and analysis',
  flows: ['vps-orchestration', 'infrastructure'],
  method: 'POST',
  path: '/api/agents/performance-monitor/execute',
  emits: [],

  bodySchema: z.object({
    metrics: z.array(z.enum(['cpu', 'memory', 'disk', 'network', 'all'])).default(['all']),
    threshold_alerts: z.boolean().default(true),
    optimization_suggestions: z.boolean().default(true),
  }),

  responseSchema: {
    200: z.object({
      metrics: z.object({
        cpu: z.object({
          usage_percent: z.number(),
          load_average: z.array(z.number()),
          top_processes: z.array(z.object({
            pid: z.number(),
            name: z.string(),
            cpu_percent: z.number(),
          })),
        }).optional(),
        memory: z.object({
          total_mb: z.number(),
          used_mb: z.number(),
          free_mb: z.number(),
          usage_percent: z.number(),
          swap_used_mb: z.number(),
        }).optional(),
        disk: z.object({
          total_gb: z.number(),
          used_gb: z.number(),
          available_gb: z.number(),
          usage_percent: z.number(),
          io_wait: z.number().optional(),
        }).optional(),
        network: z.object({
          rx_mbps: z.number(),
          tx_mbps: z.number(),
          connections: z.number(),
          bandwidth_usage_percent: z.number(),
        }).optional(),
      }),
      alerts: z.array(z.object({
        metric: z.string(),
        current_value: z.number(),
        threshold: z.number(),
        severity: z.string(),
        message: z.string(),
      })),
      bottlenecks: z.array(z.string()),
      optimization_recommendations: z.array(z.string()),
      health_score: z.number().min(0).max(100),
      metadata: z.object({
        duration_ms: z.number(),
        model_used: z.string(),
      }),
    }),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { metrics, threshold_alerts, optimization_suggestions } = req.body;

  logger.info('Performance monitor starting', { metrics });

  const startTime = Date.now();

  try {
    // Collect performance metrics
    const cpuInfo = await execAsync('top -bn1 | head -20');
    const memInfo = await execAsync('free -m');
    const diskInfo = await execAsync('df -h /');
    const loadAvg = await execAsync('uptime');

    // Parse CPU metrics
    const cpuMatch = cpuInfo.stdout.match(/Cpu\(s\):\s*([\d.]+)\s*us/);
    const cpuUsage = cpuMatch ? parseFloat(cpuMatch[1]) : 0;

    const loadMatch = loadAvg.stdout.match(/load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)/);
    const loadAverage = loadMatch
      ? [parseFloat(loadMatch[1]), parseFloat(loadMatch[2]), parseFloat(loadMatch[3])]
      : [0, 0, 0];

    // Parse memory
    const memMatch = memInfo.stdout.match(/Mem:\s+(\d+)\s+(\d+)\s+(\d+)/);
    const totalMem = memMatch ? parseInt(memMatch[1]) : 0;
    const usedMem = memMatch ? parseInt(memMatch[2]) : 0;
    const freeMem = memMatch ? parseInt(memMatch[3]) : 0;
    const memUsagePercent = totalMem > 0 ? (usedMem / totalMem) * 100 : 0;

    // Parse disk
    const diskMatch = diskInfo.stdout.match(/\s+(\d+)G\s+(\d+)G\s+(\d+)G\s+(\d+)%/);
    const totalDisk = diskMatch ? parseInt(diskMatch[1]) : 0;
    const usedDisk = diskMatch ? parseInt(diskMatch[2]) : 0;
    const availDisk = diskMatch ? parseInt(diskMatch[3]) : 0;
    const diskUsagePercent = diskMatch ? parseInt(diskMatch[4]) : 0;

    // Build analysis prompt
    const prompt = `Analyze VPS performance metrics and identify issues:

CPU Usage: ${cpuUsage.toFixed(1)}%
Load Average: ${loadAverage.join(', ')}
Memory: ${usedMem}MB used / ${totalMem}MB total (${memUsagePercent.toFixed(1)}%)
Disk: ${usedDisk}GB used / ${totalDisk}GB total (${diskUsagePercent}%)

Top Processes:
${cpuInfo.stdout.substring(0, 1000)}

Provide:
1. Performance bottlenecks
2. Alert-worthy metrics (CPU>80%, Memory>90%, Disk>85%)
3. Optimization recommendations
4. Overall health score (0-100)
5. Trend analysis

Health score criteria:
- 90-100: Excellent
- 70-89: Good
- 50-69: Fair (needs attention)
- 0-49: Poor (immediate action)`;

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
        system: 'You are a performance engineer. Analyze system metrics and provide optimization recommendations.',
        stream: false,
        options: { temperature: 0.4 },
      }),
    });

    if (!ollamaResponse.ok) {
      throw new Error('Performance analysis failed');
    }

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    // Extract bottlenecks
    const bottlenecks: string[] = [];
    const bottleneckMatches = responseText.matchAll(/bottleneck:?\s*([^\n]+)/gi);
    for (const match of bottleneckMatches) {
      bottlenecks.push(match[1].trim());
    }

    // Generate alerts based on thresholds
    const alerts: any[] = [];

    if (cpuUsage > 80) {
      alerts.push({
        metric: 'CPU',
        current_value: cpuUsage,
        threshold: 80,
        severity: cpuUsage > 95 ? 'critical' : 'high',
        message: `CPU usage at ${cpuUsage.toFixed(1)}% - investigate high-usage processes`,
      });
    }

    if (memUsagePercent > 90) {
      alerts.push({
        metric: 'Memory',
        current_value: memUsagePercent,
        threshold: 90,
        severity: memUsagePercent > 95 ? 'critical' : 'high',
        message: `Memory usage at ${memUsagePercent.toFixed(1)}% - risk of OOM`,
      });
    }

    if (diskUsagePercent > 85) {
      alerts.push({
        metric: 'Disk',
        current_value: diskUsagePercent,
        threshold: 85,
        severity: diskUsagePercent > 95 ? 'critical' : 'high',
        message: `Disk usage at ${diskUsagePercent}% - cleanup needed`,
      });
    }

    // Extract optimization recommendations
    const recommendations: string[] = [];
    const recMatches = responseText.matchAll(/(?:recommend|suggestion|optimize):?\s*([^\n]+)/gi);
    for (const match of recMatches) {
      recommendations.push(match[1].trim());
    }

    // Calculate health score (simple algorithm)
    let healthScore = 100;
    healthScore -= (cpuUsage > 80 ? (cpuUsage - 80) : 0);
    healthScore -= (memUsagePercent > 80 ? (memUsagePercent - 80) : 0);
    healthScore -= (diskUsagePercent > 80 ? (diskUsagePercent - 80) : 0);
    healthScore = Math.max(0, Math.min(100, healthScore));

    const duration = Date.now() - startTime;

    const result = {
      metrics: {
        cpu: {
          usage_percent: parseFloat(cpuUsage.toFixed(2)),
          load_average: loadAverage,
          top_processes: [],  // Would parse from top output
        },
        memory: {
          total_mb: totalMem,
          used_mb: usedMem,
          free_mb: freeMem,
          usage_percent: parseFloat(memUsagePercent.toFixed(2)),
          swap_used_mb: 0,  // Would parse from free output
        },
        disk: {
          total_gb: totalDisk,
          used_gb: usedDisk,
          available_gb: availDisk,
          usage_percent: diskUsagePercent,
        },
        network: {
          rx_mbps: 0,  // Would collect from network stats
          tx_mbps: 0,
          connections: 0,
          bandwidth_usage_percent: 0,
        },
      },
      alerts,
      bottlenecks,
      optimization_recommendations: recommendations.slice(0, 10),
      health_score: Math.round(healthScore),
      metadata: {
        duration_ms: duration,
        model_used: 'deepseek-v3.1:671b',
      },
    };

    logger.info('Performance monitoring completed', {
      healthScore,
      alertsTriggered: alerts.length,
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('Performance monitor failed', { error: error.message });

    return {
      status: 500,
      body: { error: 'Performance monitoring failed' },
    };
  }
};
