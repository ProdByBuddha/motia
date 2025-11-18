import { EventConfig, Handlers } from 'motia'
import { z } from 'zod'

export const config: EventConfig = {
  type: 'event',
  name: 'ServiceEvent',
  description: 'Handle events from other VPS services',
  flows: ['vps-orchestration'],
  subscribes: ['vps.service.event'],
  emits: [],
  input: z.object({
    source: z.string(),
    type: z.string(),
    data: z.any(),
  }),
}

export const handler: Handlers['ServiceEvent'] = async (input: any, { logger }: any) => {
  logger.info('Received service event', {
    source: input.source,
    type: input.type,
  })

  // Handle different event types
  switch (input.type) {
    case 'email.received':
      logger.info('Processing email event from BillionMail', { data: input.data })
      break

    case 'api.request':
      logger.info('Processing API request event', { data: input.data })
      break

    case 'security.alert':
      logger.warn('Security alert detected!', { data: input.data })
      break

    default:
      logger.info('Unknown event type', { type: input.type })
  }
}
