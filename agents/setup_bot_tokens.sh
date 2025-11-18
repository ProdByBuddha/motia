#!/bin/bash

# Quick setup script for bot tokens

echo "=============================================="
echo "AUTONOMOUS AGENT SYSTEM - TOKEN SETUP"
echo "=============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root: sudo $0"
  exit 1
fi

# Create config directory
mkdir -p /etc/motia
chmod 755 /etc/motia

# Check if file exists
if [ -f /etc/motia/bot-tokens.env ]; then
  echo "⚠️  Bot tokens file already exists"
  read -p "Do you want to overwrite it? (y/n): " overwrite
  if [ "$overwrite" != "y" ]; then
    echo "Exiting without changes"
    exit 0
  fi
fi

echo ""
echo "📱 BOT TOKEN SETUP"
echo ""
echo "You need to get tokens from:"
echo "  • Discord: https://discord.com/developers/applications"
echo "  • Telegram: https://t.me/BotFather"
echo ""
echo "You can set up one or both platforms."
echo ""

# Discord token
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DISCORD BOT TOKEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
read -p "Enter Discord bot token (or press Enter to skip): " DISCORD_TOKEN

# Telegram token
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TELEGRAM BOT TOKEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
read -p "Enter Telegram bot token (or press Enter to skip): " TELEGRAM_TOKEN

# Validate at least one token
if [ -z "$DISCORD_TOKEN" ] && [ -z "$TELEGRAM_TOKEN" ]; then
  echo ""
  echo "❌ ERROR: You must provide at least one bot token"
  exit 1
fi

# Create env file
echo "# Bot tokens for Autonomous Agent System" > /etc/motia/bot-tokens.env
echo "# Generated: $(date)" >> /etc/motia/bot-tokens.env
echo "" >> /etc/motia/bot-tokens.env

if [ -n "$DISCORD_TOKEN" ]; then
  echo "DISCORD_BOT_TOKEN=$DISCORD_TOKEN" >> /etc/motia/bot-tokens.env
  echo "✅ Discord token configured"
fi

if [ -n "$TELEGRAM_TOKEN" ]; then
  echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN" >> /etc/motia/bot-tokens.env
  echo "✅ Telegram token configured"
fi

# Set secure permissions
chmod 600 /etc/motia/bot-tokens.env
chown root:root /etc/motia/bot-tokens.env

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ CONFIGURATION COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Token file created: /etc/motia/bot-tokens.env"
echo "Permissions set to 600 (secure)"
echo ""
echo "Next steps:"
echo "  1. Install systemd service:"
echo "     sudo cp /tmp/agent-bots.service /etc/systemd/system/"
echo "     sudo systemctl daemon-reload"
echo ""
echo "  2. Enable auto-start:"
echo "     sudo systemctl enable agent-bots.service"
echo "     sudo systemctl enable superqwen-parlant.service"
echo ""
echo "  3. Start services:"
echo "     sudo systemctl start superqwen-parlant.service"
echo "     sudo systemctl start agent-bots.service"
echo ""
echo "  4. View logs:"
echo "     sudo journalctl -u agent-bots.service -f"
echo ""
echo "For full documentation, see:"
echo "  /opt/motia/agents/AUTONOMOUS_AGENT_SYSTEM.md"
echo ""
