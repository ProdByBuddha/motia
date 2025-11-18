import { CronConfig, Handlers } from 'motia'
import axios from 'axios'

export const config: CronConfig = {
  type: 'cron',
  name: 'HealthMonitor',
  description: 'Monitor health of all VPS services',
  cron: '*/5 * * * *', // Every 5 minutes
  emits: [],
  flows: ['vps-orchestration'],
}

export const handler: Handlers['HealthMonitor'] = async ({ logger }: any) => {
  const services = [
    { name: 'Traefik', url: 'http://traefik:8080/ping' },
    { name: 'Homepage', url: 'http://homepage:3000' },
    // Ollama Cloud is external - health check via proxy not needed
    // { name: 'Ollama', url: 'http://ollama:11434' },
    { name: 'Wix Backend', url: 'http://wix-backend:3000/api/health' },
  ]

  logger.info('Starting health check for all services')

  const results = await Promise.allSettled(
    services.map(async (service) => {
      try {
        const response = await axios.get(service.url, { timeout: 5000 })
        return {
          name: service.name,
          status: 'healthy',
          statusCode: response.status,
        }
      } catch (error: any) {
        return {
          name: service.name,
          status: 'unhealthy',
          error: error.message,
        }
      }
    })
  )

  const healthReport = results.map((result, index) => ({
    service: services[index].name,
    ...(result.status === 'fulfilled' ? result.value : { status: 'error', error: result.reason }),
  }))

  const unhealthyServices = healthReport.filter(s => s.status !== 'healthy')

  if (unhealthyServices.length > 0) {
    logger.warn('Unhealthy services detected', { unhealthyServices })
  } else {
    logger.info('All services healthy', { totalServices: services.length })
  }
}
