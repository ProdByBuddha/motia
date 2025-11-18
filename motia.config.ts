module.exports = {
  name: 'VPS Orchestration Service',
  version: '1.0.0',

  // Server configuration
  server: {
    port: parseInt(process.env.MOTIA_PORT || '3000'),
    host: process.env.MOTIA_HOST || '0.0.0.0',
  },

  // Steps directory configuration
  steps: {
    dir: './steps',
    watch: true,
  },

  // Disable workbench UI for production
  workbench: {
    enabled: false,
    path: '/_workbench',
  },

  // Service integrations
  integrations: {
    postgres: {
      host: process.env.POSTGRES_HOST || 'localhost',
      port: parseInt(process.env.POSTGRES_PORT || '5432'),
      user: process.env.POSTGRES_USER || 'postgres',
      password: process.env.POSTGRES_PASSWORD || 'postgres',
      database: process.env.POSTGRES_DB || 'billionmail',
    },
    redis: {
      host: process.env.REDIS_HOST || 'localhost',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      password: process.env.REDIS_PASSWORD,
    },
    ollama: {
      host: process.env.OLLAMA_HOST || 'http://localhost:11434',
    },
  },

  // Workflow orchestration engine
  workflowEngine: {
    enabled: true,
    stateStorage: 'postgres',
    executionTimeout: 600000,  // 10 minutes default
    maxConcurrentExecutions: 50,
  },

  // Agent registry
  agentRegistry: {
    enabled: true,
    discoveryPath: './steps/agents',
    autoRegister: true,
  },

  // Observability
  observability: {
    logging: {
      level: process.env.LOG_LEVEL || 'info',
      format: 'json',
    },
    metrics: {
      enabled: true,
      port: 9090,
    },
  },

  // Security
  security: {
    cors: {
      enabled: true,
      origin: ['https://vps.iameternalzion.com', 'https://lab.iameternalzion.com'],
    },
    rateLimit: {
      enabled: true,
      max: 100,
      windowMs: 60000, // 1 minute
    },
  },
}
