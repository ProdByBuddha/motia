/**
 * Custom Motia Server with Streaming Proxy Middleware
 *
 * This starts Motia but registers streaming proxy middleware BEFORE Motia's router
 * to enable proper streaming from Ollama Cloud.
 */

import { createEventManager, createServer, createStateAdapter } from '@motiadev/core';
import path from 'path';
import { generateLockedData } from '../node_modules/motia/dist/esm/generate-locked-data.js';
import { createDevWatchers } from '../node_modules/motia/dist/esm/dev-watchers.js';
import { createOllamaStreamingProxy } from './proxy-middleware';

const PORT = parseInt(process.env.MOTIA_PORT || '3000');
const HOST = process.env.MOTIA_HOST || '0.0.0.0';

async function start() {
  const baseDir = process.cwd();

  console.log('🔧 Initializing custom Motia server with streaming proxy...');

  // Generate locked data from steps
  const lockedData = await generateLockedData(baseDir);

  // Create Motia components
  const eventManager = createEventManager();
  const state = createStateAdapter({
    adapter: 'default',
    filePath: path.join(baseDir, '.motia'),
  });

  // Create Motia server
  const motiaServer = createServer(lockedData, eventManager, state, { isVerbose: true });

  // ⚡ REGISTER STREAMING PROXY MIDDLEWARE FIRST (before Motia router)
  const streamingProxy = createOllamaStreamingProxy();
  motiaServer.app.use(streamingProxy);
  console.log('✓ Streaming proxy middleware registered');

  // Initialize watchers for hot reload
  const watcher = createDevWatchers(
    lockedData,
    motiaServer,
    motiaServer.motiaEventManager,
    motiaServer.cronManager
  );
  watcher.init();

  // Start server
  motiaServer.server.listen(PORT, HOST);
  console.log(`🚀 Server ready and listening on ${HOST}:${PORT}`);
  console.log(`🔗 Streaming proxy: http://localhost:${PORT}/api/ollama/api/*`);

  // Graceful shutdown
  process.on('SIGTERM', async () => {
    motiaServer.server.close();
    await watcher.stop();
    process.exit(0);
  });

  process.on('SIGINT', async () => {
    motiaServer.server.close();
    await watcher.stop();
    process.exit(0);
  });
}

start().catch((error) => {
  console.error('Failed to start server:', error);
  process.exit(1);
});
