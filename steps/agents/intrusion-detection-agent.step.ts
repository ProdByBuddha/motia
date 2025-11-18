/**
 * Intrusion Detection Agent (IDS)
 *
 * Real-time intrusion detection using deepseek-v3.1:671b for threat analysis.
 * Monitors auth logs, network connections, processes for suspicious activity.
 */

import { z } from 'zod';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const config = {
  type: 'api',
  name: 'IntrusionDetectionAgent',
  description: 'Real-time intrusion detection and threat analysis',
  flows: ['vps-orchestration', 'security'],
  method: 'POST',
  path: '/api/agents/intrusion-detection/execute',
  emits: [],

  bodySchema: z.object({
    scan_type: z.enum(['quick', 'comprehensive', 'targeted']).default('quick'),
    target_logs: z.array(z.string()).optional().describe('Specific log files to analyze'),
    time_window: z.string().default('1h').describe('Time window: 1h, 24h, 7d'),
  }),

  responseSchema: {
    200: z.object({
      threats_detected: z.array(z.object({
        threat_id: z.string(),
        severity: z.enum(['critical', 'high', 'medium', 'low']),
        threat_type: z.string(),
        source_ip: z.string().optional(),
        target: z.string(),
        timestamp: z.string(),
        evidence: z.string(),
        recommended_action: z.string(),
        confidence: z.number(),
      })),
      summary: z.object({
        total_threats: z.number(),
        critical_count: z.number(),
        high_count: z.number(),
        medium_count: z.number(),
        low_count: z.number(),
        auto_blocked: z.number(),
      }),
      system_status: z.enum(['secure', 'at_risk', 'compromised', 'under_attack']),
      recommendations: z.array(z.string()),
      metadata: z.object({
        duration_ms: z.number(),
        model_used: z.string(),
        logs_analyzed: z.number(),
      }),
    }),
    400: z.object({ error: z.string() }),
    500: z.object({ error: z.string() }),
  },
};

export const handler = async (req: any, { logger }: any) => {
  const { scan_type, target_logs, time_window } = req.body;

  logger.info('IDS agent starting', { scan_type, time_window });

  const startTime = Date.now();

  try {
    // Collect security data from VPS
    const authLog = await execAsync('tail -1000 /var/log/auth.log 2>/dev/null || echo "No auth log"');
    const failedLogins = await execAsync('grep "Failed password" /var/log/auth.log 2>/dev/null | tail -100 || echo "No failures"');
    const activeConnections = await execAsync('netstat -tunapl 2>/dev/null | grep ESTABLISHED || echo "No connections"');
    const suspiciousProcesses = await execAsync('ps aux | grep -E "(nc|ncat|nmap|masscan|nikto)" || echo "No suspicious processes"');

    // Build analysis prompt with collected data
    const prompt = `Analyze this VPS for security threats and intrusions:

Time Window: ${time_window}
Scan Type: ${scan_type}

=== AUTHENTICATION LOG (last 1000 lines) ===
${authLog.stdout.substring(0, 3000)}

=== FAILED LOGIN ATTEMPTS (last 100) ===
${failedLogins.stdout.substring(0, 2000)}

=== ACTIVE NETWORK CONNECTIONS ===
${activeConnections.stdout.substring(0, 1500)}

=== SUSPICIOUS PROCESSES ===
${suspiciousProcesses.stdout.substring(0, 500)}

Provide comprehensive intrusion detection analysis:
1. Identify any active threats or attacks
2. Classify threat severity (critical/high/medium/low)
3. Determine threat types (brute force, port scan, malware, etc.)
4. Extract source IPs and targets
5. Assess system security status
6. Recommend immediate actions

Format as:
THREATS DETECTED:
- [SEVERITY] Threat Type from IP → Target (Evidence) → Action needed

SYSTEM STATUS: [secure|at_risk|compromised|under_attack]
RECOMMENDATIONS: [actions]`;

    const ollamaApiKey = process.env.OLLAMA_API_KEY ||
                         'c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g';

    logger.info('Analyzing security data with deepseek-v3.1:671b');

    const ollamaResponse = await fetch('https://ollama.com/api/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ollamaApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'deepseek-v3.1:671b',
        prompt,
        system: 'You are a cybersecurity expert specializing in intrusion detection. Analyze system data for security threats with high accuracy.',
        stream: false,
        options: {
          temperature: 0.3,  // Low temp for security - need accuracy
          num_predict: 2000,
        },
      }),
    });

    if (!ollamaResponse.ok) {
      throw new Error('IDS analysis failed');
    }

    const ollamaResult = await ollamaResponse.json();
    const responseText = ollamaResult.response || '';

    logger.info('IDS analysis complete', { responseLength: responseText.length });

    // Parse threats from response
    const threats: any[] = [];
    const threatPattern = /\[?(CRITICAL|HIGH|MEDIUM|LOW)\]?\s+([^:]+):\s*([^\n]+)/gi;
    let match;
    let threatId = 1;

    while ((match = threatPattern.exec(responseText)) !== null) {
      const severity = match[1].toLowerCase();
      const threatType = match[2].trim();
      const evidence = match[3].trim();

      // Extract IP if present
      const ipMatch = evidence.match(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/);
      const sourceIp = ipMatch ? ipMatch[1] : undefined;

      threats.push({
        threat_id: `IDS-${Date.now()}-${threatId++}`,
        severity,
        threat_type: threatType,
        source_ip: sourceIp,
        target: 'VPS',
        timestamp: new Date().toISOString(),
        evidence: evidence.substring(0, 200),
        recommended_action: severity === 'critical' || severity === 'high'
          ? 'Immediate investigation and blocking required'
          : 'Monitor and review',
        confidence: severity === 'critical' ? 0.95 : severity === 'high' ? 0.85 : 0.70,
      });
    }

    // Determine system status
    const criticalCount = threats.filter(t => t.severity === 'critical').length;
    const highCount = threats.filter(t => t.severity === 'high').length;
    const mediumCount = threats.filter(t => t.severity === 'medium').length;
    const lowCount = threats.filter(t => t.severity === 'low').length;

    let systemStatus = 'secure';
    if (criticalCount > 0) systemStatus = 'compromised';
    else if (highCount > 2) systemStatus = 'under_attack';
    else if (highCount > 0 || mediumCount > 5) systemStatus = 'at_risk';

    // Extract recommendations
    const recommendations: string[] = [];
    const recMatch = responseText.match(/RECOMMENDATIONS?:([^\n]+(?:\n[-*]\s*[^\n]+)*)/i);

    if (recMatch) {
      const recLines = recMatch[1].split('\n');
      for (const line of recLines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('-') || trimmed.startsWith('*')) {
          recommendations.push(trimmed.replace(/^[-*]\s*/, ''));
        }
      }
    }

    // Add default recommendations based on findings
    if (criticalCount > 0) {
      recommendations.unshift('URGENT: Investigate critical threats immediately');
    }
    if (highCount > 5) {
      recommendations.unshift('Possible active attack - enable auto-blocking');
    }

    const logsAnalyzed =
      authLog.stdout.split('\n').length +
      failedLogins.stdout.split('\n').length +
      activeConnections.stdout.split('\n').length;

    const duration = Date.now() - startTime;

    const result = {
      threats_detected: threats.slice(0, 50),  // Top 50 threats
      summary: {
        total_threats: threats.length,
        critical_count: criticalCount,
        high_count: highCount,
        medium_count: mediumCount,
        low_count: lowCount,
        auto_blocked: 0,  // Would track actual blocks in production
      },
      system_status: systemStatus,
      recommendations: recommendations.slice(0, 10),
      metadata: {
        duration_ms: duration,
        model_used: 'deepseek-v3.1:671b',
        logs_analyzed: logsAnalyzed,
      },
    };

    logger.info('IDS analysis completed', {
      threatsFound: threats.length,
      systemStatus,
      duration,
    });

    return {
      status: 200,
      body: result,
    };

  } catch (error: any) {
    logger.error('IDS agent failed', { error: error.message });

    return {
      status: 500,
      body: {
        error: 'Intrusion detection failed',
        details: { message: error.message },
      },
    };
  }
};

/**
 * Example usage:
 *
 * POST /api/agents/intrusion-detection/execute
 *
 * {
 *   "scan_type": "comprehensive",
 *   "time_window": "24h"
 * }
 *
 * Response:
 * {
 *   "threats_detected": [
 *     {
 *       "threat_id": "IDS-1730901234-1",
 *       "severity": "high",
 *       "threat_type": "Brute Force Attack",
 *       "source_ip": "192.168.1.100",
 *       "target": "SSH Service",
 *       "timestamp": "2025-11-06T06:30:00Z",
 *       "evidence": "127 failed login attempts in 5 minutes",
 *       "recommended_action": "Block IP immediately",
 *       "confidence": 0.95
 *     }
 *   ],
 *   "summary": {
 *     "total_threats": 5,
 *     "critical_count": 0,
 *     "high_count": 2,
 *     "medium_count": 2,
 *     "low_count": 1
 *   },
 *   "system_status": "at_risk",
 *   "recommendations": [
 *     "Enable fail2ban for SSH protection",
 *     "Review firewall rules",
 *     "Implement rate limiting"
 *   ]
 * }
 */
