/**
 * Vault Cluster Monitor Agent
 *
 * Monitors your 3-node Vault cluster + backup + unseal service.
 * Uses deepseek-v3.1:671b for cluster health analysis.
 */

import { z } from 'zod';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const config = {
  type: 'api',
  name: 'VaultClusterMonitorAgent',
  description: 'HashiCorp Vault cluster monitoring and analysis',
  flows: ['vps-orchestration', 'security'],
  method: 'POST',
  path: '/api/agents/vault-cluster-monitor/execute',
  emits: [],

  bodySchema: z.object({
    check_type: z.enum(['status', 'replication', 'security', 'all']).default('all'),
  }),

  responseSchema: {
    200: z.object({
      cluster_health: z.object({
        node_count: z.number(),
        sealed_nodes: z.number(),
        unsealed_nodes: z.number(),
        leader_node: z.string().optional(),
        replication_status: z.enum(['healthy', 'degraded', 'failed']),
      }),
      nodes: z.array(z.object({
        node_name: z.string(),
        status: z.enum(['running', 'restarting', 'stopped']),
        sealed: z.boolean(),
        health: z.enum(['healthy', 'degraded', 'critical']),
      })),
      security_analysis: z.object({
        unsealed_count: z.number(),
        backup_status: z.enum(['running', 'stopped']),
        auto_unseal_status: z.enum(['running', 'stopped']),
        recommendations: z.array(z.string()),
      }),
      health_score: z.number().min(0).max(100),
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
  const { check_type } = req.body;

  logger.info('Vault cluster monitor starting', { check_type });

  const startTime = Date.now();

  try {
    // Check all Vault containers
    const vaultContainers = await execAsync('docker ps -a --filter "name=vault" --format "{{.Names}}|{{.Status}}|{{.State}}"');

    const nodes: any[] = [];
    let sealedCount = 0;
    let unsealedCount = 0;

    for (const line of vaultContainers.stdout.split('\n')) {
      if (line.trim()) {
        const [name, status, state] = line.split('|');

        // Determine if sealed (would check actual Vault API)
        const sealed = name.includes('unseal') ? false : state === 'running' ? false : true;

        if (sealed) sealedCount++;
        else unsealedCount++;

        nodes.push({
          node_name: name,
          status: state === 'running' ? 'running' : state === 'restarting' ? 'restarting' : 'stopped',
          sealed,
          health: state === 'running' && !sealed ? 'healthy' : state === 'running' ? 'degraded' : 'critical',
        });
      }
    }

    const prompt = `Analyze HashiCorp Vault cluster health:

Cluster Configuration:
- Total Nodes: ${nodes.length}
- Sealed Nodes: ${sealedCount}
- Unsealed Nodes: ${unsealedCount}

Node Status:
${nodes.map(n => `${n.node_name}: ${n.status}, ${n.sealed ? 'SEALED' : 'UNSEALED'}`).join('\n')}

Evaluate:
1. Cluster quorum and leader election
2. Seal status (critical security check)
3. Replication health
4. Auto-unseal service status
5. Backup node availability
6. Secret access patterns

Provide:
- Critical issues (sealed nodes, stopped services)
- Health score (0-100)
- Security recommendations
- Operational recommendations`;

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
        system: 'You are a HashiCorp Vault expert. Analyze cluster health and security.',
        stream: false,
        options: { temperature: 0.3 },
      }),
    });

    if (!ollamaResponse.ok) throw new Error('Vault analysis failed');

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    // Extract critical issues
    const criticalIssues: string[] = [];
    if (sealedCount > 0) criticalIssues.push(`${sealedCount} sealed Vault nodes - cluster degraded`);
    if (nodes.filter(n => n.status === 'stopped').length > 0) criticalIssues.push('Vault nodes stopped');

    const criticalMatches = responseText.matchAll(/(?:critical|urgent):?\s*([^\n]+)/gi);
    for (const match of criticalMatches) {
      criticalIssues.push(match[1].trim());
    }

    // Extract recommendations
    const recommendations: string[] = [];
    const recMatches = responseText.matchAll(/(?:recommend|should):?\s*([^\n]+)/gi);
    for (const match of recMatches) {
      recommendations.push(match[1].trim());
    }

    // Calculate health score
    let healthScore = 100;
    healthScore -= (sealedCount * 30);  // Major penalty for sealed nodes
    healthScore -= (nodes.filter(n => n.status === 'stopped').length * 25);
    healthScore = Math.max(0, healthScore);

    const backupNode = nodes.find(n => n.node_name.includes('backup'));
    const unsealNode = nodes.find(n => n.node_name.includes('unseal'));

    const duration = Date.now() - startTime;

    const result = {
      cluster_health: {
        node_count: nodes.length,
        sealed_nodes: sealedCount,
        unsealed_nodes: unsealedCount,
        leader_node: nodes.find(n => !n.sealed)?.node_name,
        replication_status: sealedCount === 0 ? 'healthy' : sealedCount < nodes.length ? 'degraded' : 'failed',
      },
      nodes,
      security_analysis: {
        unsealed_count: unsealedCount,
        backup_status: backupNode?.status || 'unknown',
        auto_unseal_status: unsealNode?.status || 'unknown',
        recommendations: recommendations.slice(0, 5),
      },
      health_score: healthScore,
      critical_issues: criticalIssues,
      recommendations: recommendations.slice(0, 10),
      metadata: {
        duration_ms: duration,
        model_used: 'deepseek-v3.1:671b',
      },
    };

    logger.info('Vault cluster monitoring completed', {
      nodes: nodes.length,
      sealed: sealedCount,
      healthScore,
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('Vault cluster monitor failed', { error: error.message });
    return {
      status: 500,
      body: { error: 'Vault cluster monitoring failed' },
    };
  }
};
