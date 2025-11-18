#!/usr/bin/env python3
"""
Unified Bot Launcher

Starts the complete autonomous agent system with:
- Agent coordination system
- Discord bot integration
- Telegram bot integration
- Cross-platform persistent memory (Redis)

All platforms share the same agent system and memory.
"""

import asyncio
import os
import signal
import sys

sys.path.insert(0, '/opt/motia/agents/shared')
sys.path.insert(0, '/opt/motia/agents/platforms')

from agent_coordinator import create_agent_coordinator
from discord_bot import start_discord_bot
from telegram_bot import start_telegram_bot


class UnifiedBotLauncher:
    """Unified launcher for all bot platforms"""

    def __init__(self):
        self.coordinator = None
        self.discord_bot = None
        self.telegram_bot = None
        self.running = False

    async def start(self):
        """Start all systems"""
        print("=" * 80)
        print("AUTONOMOUS AGENT SYSTEM")
        print("Multi-Platform Dev Agency Coordinator")
        print("=" * 80)
        print()

        # Initialize coordinator
        print("[Launcher] Initializing agent coordinator...")
        self.coordinator = await create_agent_coordinator()
        print("[Launcher] ✅ Agent coordinator ready")
        print()

        # Get bot tokens from environment
        discord_token = os.getenv('DISCORD_BOT_TOKEN')
        telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')

        # Start Discord bot if token available
        if discord_token:
            print("[Launcher] Starting Discord bot...")
            discord_task = asyncio.create_task(
                start_discord_bot(self.coordinator, discord_token)
            )
            print("[Launcher] ✅ Discord bot started")
        else:
            print("[Launcher] ⚠️  DISCORD_BOT_TOKEN not set, skipping Discord")
            discord_task = None

        # Start Telegram bot if token available
        if telegram_token:
            print("[Launcher] Starting Telegram bot...")
            self.telegram_bot = await start_telegram_bot(self.coordinator, telegram_token)
            print("[Launcher] ✅ Telegram bot started")
        else:
            print("[Launcher] ⚠️  TELEGRAM_BOT_TOKEN not set, skipping Telegram")

        print()
        print("=" * 80)
        print("✅ SYSTEM READY")
        print("=" * 80)
        print()
        print("Connected Platforms:")
        if discord_token:
            print("  ✅ Discord")
        if telegram_token:
            print("  ✅ Telegram")
        print()
        print("Agent Team:")
        for role, agent in self.coordinator.agents.items():
            print(f"  🤖 {role.value.replace('_', ' ').title()}")
        print()
        print("SuperQwen Features:")
        try:
            if hasattr(self.coordinator, "orchestrator") and self.coordinator.orchestrator:
                avail = self.coordinator.orchestrator.get_available_agents()
                py_count = len(avail.get("python_pydantic", []))
            else:
                # Fallback to direct registry
                py_count = len(getattr(self.coordinator, "pydantic_agents", {}))
        except Exception:
            py_count = len(getattr(self.coordinator, "pydantic_agents", {}))
        print(f"  📚 {py_count} Pydantic AI agents")
        print(f"  🎭 13 SuperQwen personas")
        print(f"  ⚡ 17 command workflows")
        print()
        print("Memory:")
        print("  💾 Redis (persistent across platforms)")
        print("  🔄 Cross-platform conversation sync")
        print()
        print("Ready to build! 🚀")
        print()

        self.running = True

        # Keep running
        try:
            if discord_task:
                await discord_task
            else:
                # Just keep the telegram bot running
                while self.running:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("\n[Launcher] Shutting down...")
            await self.stop()

    async def stop(self):
        """Stop all systems gracefully"""
        self.running = False

        if self.telegram_bot:
            print("[Launcher] Stopping Telegram bot...")
            await self.telegram_bot.stop()

        if self.coordinator:
            if self.coordinator.redis_client:
                await self.coordinator.redis_client.aclose()

        print("[Launcher] ✅ Shutdown complete")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\n[Launcher] Received shutdown signal")
        if self.running:
            asyncio.create_task(self.stop())


async def main():
    """Main entry point"""
    launcher = UnifiedBotLauncher()

    # Setup signal handlers
    signal.signal(signal.SIGINT, launcher.signal_handler)
    signal.signal(signal.SIGTERM, launcher.signal_handler)

    try:
        await launcher.start()
    except KeyboardInterrupt:
        print("\n[Launcher] Keyboard interrupt")
        await launcher.stop()
    except Exception as e:
        print(f"[Launcher] Error: {e}")
        import traceback
        traceback.print_exc()
        await launcher.stop()


if __name__ == '__main__':
    # Set default Redis URL if not set
    if 'REDIS_URL' not in os.environ:
        os.environ['REDIS_URL'] = 'redis://localhost:6380/0'

    # Check for bot tokens
    if not os.getenv('DISCORD_BOT_TOKEN') and not os.getenv('TELEGRAM_BOT_TOKEN'):
        print("=" * 80)
        print("ERROR: No bot tokens configured")
        print("=" * 80)
        print()
        print("Please set at least one of:")
        print("  export DISCORD_BOT_TOKEN='your_discord_token'")
        print("  export TELEGRAM_BOT_TOKEN='your_telegram_token'")
        print()
        print("To get bot tokens:")
        print("  Discord: https://discord.com/developers/applications")
        print("  Telegram: https://t.me/BotFather")
        print()
        sys.exit(1)

    # Run the launcher
    asyncio.run(main())
