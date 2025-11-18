/**
 * Hybrid Ollama Provider with sns-core Compression
 * Container-agnostic implementation for TypeScript/JavaScript
 *
 * Usage:
 *   import { HybridOllamaProvider, OperationType } from './hybrid-ollama';
 *
 *   // Background agent (CI/CD) - uses local Ollama
 *   const bgProvider = new HybridOllamaProvider(OperationType.BACKGROUND);
 *
 *   // User-facing agent (Parlant) - uses Ollama Cloud
 *   const ufProvider = new HybridOllamaProvider(OperationType.USER_FACING);
 */

export enum OperationType {
  BACKGROUND = 'background',     // CI/CD agents → Local Ollama ($0, 5-10s)
  USER_FACING = 'user_facing',   // Conversational → Ollama Cloud (<1s, minimal cost)
}

export interface HybridOllamaConfig {
  baseUrl: string;
  model: string;
  timeout: number;
  operationType: OperationType;
  snsCore Enabled: boolean;
  headers?: Record<string, string>;
}

export interface HybridOllamaStats {
  backend: string;
  endpoint: string;
  model: string;
  operationType: string;
  latencyTarget: string;
  cost: string;
  snsCoreEnabled: boolean;
  compressionRate: string;
  timeout: number;
}

export class HybridOllamaProvider {
  private baseUrl: string;
  private model: string;
  private apiKey?: string;
  private timeout: number;
  private operationType: OperationType;
  private snsCoreEnabled: boolean;
  private latencyTarget: string;
  private cost: string;

  constructor(
    operationType: OperationType = OperationType.BACKGROUND,
    model?: string,
    enableSnsCore: boolean = true,
    customConfig?: Partial<HybridOllamaConfig>
  ) {
    this.operationType = operationType;
    this.model = model || process.env.OLLAMA_MODEL || 'qwen2.5:7b-instruct';
    this.snsCoreEnabled = enableSnsCore;

    // Configure backend based on operation type
    this.configureBackend();

    // Apply custom config overrides
    if (customConfig) {
      Object.assign(this, customConfig);
    }
  }

  private configureBackend(): void {
    const isDocker = process.env.RUNNING_IN_DOCKER === 'true';

    if (this.operationType === OperationType.BACKGROUND) {
      // Use local Ollama for background operations
      let baseUrl = process.env.OLLAMA_LOCAL_URL || 'http://localhost:11434';

      // Docker environment: replace localhost with host.docker.internal
      if (isDocker) {
        baseUrl = baseUrl.replace('localhost', 'host.docker.internal');
        baseUrl = baseUrl.replace('127.0.0.1', 'host.docker.internal');
      }

      this.baseUrl = baseUrl;
      this.apiKey = undefined;
      this.timeout = 60000; // 60 seconds
      this.latencyTarget = '5-10s';
      this.cost = '$0';
    } else {
      // Use Ollama Cloud for user-facing operations
      const baseUrl = process.env.OLLAMA_CLOUD_URL || 'https://api.ollama.com';
      const apiKey = process.env.OLLAMA_CLOUD_API_KEY;

      this.baseUrl = baseUrl;
      this.apiKey = apiKey;
      this.timeout = 10000; // 10 seconds
      this.latencyTarget = '<1s';
      this.cost = '~$0.0002/query';
    }
  }

  public getModelString(): string {
    /**
     * Get model string for Pydantic AI or other frameworks
     * Returns: "ollama:model_name"
     */
    return `ollama:${this.model}`;
  }

  public getConfig(): HybridOllamaConfig {
    /**
     * Get configuration object
     */
    const config: HybridOllamaConfig = {
      baseUrl: `${this.baseUrl}/api`,
      model: this.model,
      timeout: this.timeout,
      operationType: this.operationType,
      snsCoreEnabled: this.snsCoreEnabled,
    };

    // Add authorization header for Ollama Cloud
    if (this.apiKey && this.baseUrl.includes('ollama.com')) {
      config.headers = {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      };
    }

    return config;
  }

  public compressPrompt(prompt: string, context?: Record<string, any>): string {
    /**
     * Compress prompt using sns-core notation
     *
     * Args:
     *   prompt: Original prompt text
     *   context: Optional context object to compress
     *
     * Returns:
     *   Compressed prompt string
     */
    if (!this.snsCoreEnabled) {
      return prompt;
    }

    // If context provided, encode it
    if (context) {
      const encodedContext = this.encodeContext(context);
      return `${prompt}|ctx:${encodedContext}`;
    }

    return prompt;
  }

  private encodeContext(context: Record<string, any>): string {
    /**
     * Encode context using sns-core notation
     * Format: key1:val1|key2:val2|...
     */
    return Object.entries(context)
      .map(([key, value]) => {
        if (Array.isArray(value)) {
          return `${key}:${value.join(',')}`;
        }
        return `${key}:${value}`;
      })
      .join('|');
  }

  public getStats(): HybridOllamaStats {
    /**
     * Get provider statistics
     */
    return {
      backend: this.operationType === OperationType.BACKGROUND ? 'Local Ollama' : 'Ollama Cloud',
      endpoint: this.baseUrl,
      model: this.model,
      operationType: this.operationType,
      latencyTarget: this.latencyTarget,
      cost: this.cost,
      snsCoreEnabled: this.snsCoreEnabled,
      compressionRate: this.snsCoreEnabled ? '60-85%' : '0%',
      timeout: this.timeout,
    };
  }

  public toString(): string {
    const stats = this.getStats();
    return `HybridOllamaProvider(backend=${stats.backend}, model=${stats.model}, snsCore=${stats.snsCoreEnabled})`;
  }
}

/**
 * Factory for creating providers based on agent type
 */
export class HybridOllamaFactory {
  private static readonly AGENT_TYPE_MAP: Record<string, OperationType> = {
    // Background CI/CD agents → Local Ollama
    'build': OperationType.BACKGROUND,
    'test': OperationType.BACKGROUND,
    'deploy': OperationType.BACKGROUND,
    'monitor': OperationType.BACKGROUND,

    // User-facing agents → Ollama Cloud
    'parlant': OperationType.USER_FACING,
    'chat': OperationType.USER_FACING,
    'conversational': OperationType.USER_FACING,
    'interactive': OperationType.USER_FACING,
  };

  static createForAgent(
    agentType: string,
    model?: string,
    enableSnsCore: boolean = true
  ): HybridOllamaProvider {
    /**
     * Create provider for specific agent type
     *
     * Args:
     *   agentType: Agent type (build, test, deploy, monitor, parlant, chat, etc.)
     *   model: Optional model override
     *   enableSnsCore: Enable sns-core compression
     *
     * Returns:
     *   Configured HybridOllamaProvider
     */
    const operationType = this.AGENT_TYPE_MAP[agentType.toLowerCase()] || OperationType.BACKGROUND;

    return new HybridOllamaProvider(operationType, model, enableSnsCore);
  }
}

/**
 * Convenience functions for common use cases
 */
export function getBackgroundOllama(model?: string): HybridOllamaProvider {
  /** Get Ollama provider for background operations (local, free) */
  return new HybridOllamaProvider(OperationType.BACKGROUND, model);
}

export function getUserFacingOllama(model?: string): HybridOllamaProvider {
  /** Get Ollama provider for user-facing operations (cloud, fast) */
  return new HybridOllamaProvider(OperationType.USER_FACING, model);
}

// Example usage
if (require.main === module) {
  console.log('='.repeat(80));
  console.log('HYBRID OLLAMA PROVIDER TEST (TypeScript)');
  console.log('='.repeat(80));
  console.log();

  // Test background provider
  console.log('1. Background Agent Configuration (CI/CD)');
  console.log('-'.repeat(80));
  const bgProvider = getBackgroundOllama();
  console.log(bgProvider.toString());
  console.log('\nConfiguration:', JSON.stringify(bgProvider.getConfig(), null, 2));
  console.log('\nStatistics:', JSON.stringify(bgProvider.getStats(), null, 2));
  console.log();

  // Test user-facing provider
  console.log('2. User-Facing Agent Configuration (Parlant)');
  console.log('-'.repeat(80));
  const ufProvider = getUserFacingOllama();
  console.log(ufProvider.toString());
  console.log('\nConfiguration:', JSON.stringify(ufProvider.getConfig(), null, 2));
  console.log('\nStatistics:', JSON.stringify(ufProvider.getStats(), null, 2));
  console.log();

  // Test factory
  console.log('3. Factory Pattern Test');
  console.log('-'.repeat(80));
  const agentTypes = ['build', 'test', 'parlant', 'chat'];
  agentTypes.forEach((type) => {
    const provider = HybridOllamaFactory.createForAgent(type);
    const stats = provider.getStats();
    console.log(`${type.padEnd(12)} → ${stats.backend.padEnd(15)} | ${stats.cost.padEnd(12)} | ${stats.latencyTarget}`);
  });
  console.log();

  console.log('='.repeat(80));
  console.log('TEST COMPLETE');
  console.log('='.repeat(80));
}
