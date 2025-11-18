"""
Telegram Bot Integration for Agent Coordinator

Allows the lead to interact with the autonomous agent system via Telegram.
Shares memory with Discord bot through Redis.
"""

import asyncio
import json
import os
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

import sys
sys.path.insert(0, '/opt/motia/agents/shared')

from agent_coordinator import AgentCoordinator, AgentRole, ActionType


class TelegramAgentBot:
    """Telegram bot for agent coordination"""

    def __init__(self, coordinator: AgentCoordinator, token: str):
        self.coordinator = coordinator
        self.token = token
        self.app = Application.builder().token(token).build()

        # Register with coordinator
        self.coordinator.register_channel('telegram', self)

        # Setup handlers
        self.setup_handlers()

    def setup_handlers(self):
        """Setup bot command handlers"""

        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("build", self.build_command))
        self.app.add_handler(CommandHandler("task", self.task_command))
        self.app.add_handler(CommandHandler("approve", self.approve_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("pending", self.pending_command))
        self.app.add_handler(CommandHandler("agents", self.agents_command))
        self.app.add_handler(CommandHandler("talk", self.talk_command))

        # Callback query handler for inline buttons
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        # Set this user as the lead
        user_id = f"telegram:{update.effective_user.id}"
        self.coordinator.set_lead_user(user_id)

        message = """
🤖 **Welcome to Your Autonomous Agent System**

I'm your dev agency coordinator. I manage a team of AI agents who work together to build applications.

**Available Commands:**
/build - Have agents build an app
/task - Create a specific task
/approve - Approve a pending task
/status - Check task status
/pending - List pending approvals
/talk - Chat with an agent
/agents - List all agents
/help - Show detailed help

Your agents are ready. What would you like to build?
"""
        await update.message.reply_text(message, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        message = """
🤖 **Agent System Commands**

**Building Apps:**
`/build <description>` - Have agents build an application

**Task Management:**
`/task <role> <action> <description>` - Create specific task
  Roles: architect, backend_dev, frontend_dev, devops, qa, security, tech_writer
  Actions: safe, moderate, destructive

`/approve <task_id>` - Approve a pending task
`/status <task_id>` - Check task status
`/pending` - List tasks awaiting approval

**Communication:**
`/talk <role> <message>` - Chat with a specific agent
`/agents` - List all available agents

**Example:**
`/build Create a REST API for a todo app with PostgreSQL`
`/talk architect What technologies do you recommend for this project?`
`/approve task_abc123`
"""
        await update.message.reply_text(message, parse_mode='Markdown')

    async def build_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /build command"""
        if not context.args:
            await update.message.reply_text("Usage: /build <description>")
            return

        description = ' '.join(context.args)
        user_id = f"telegram:{update.effective_user.id}"

        # Create high-level task for architect
        task = await self.coordinator.create_task(
            title=f"Build: {description[:50]}",
            description=f"Design and implement: {description}",
            assigned_to=AgentRole.ARCHITECT,
            action_type=ActionType.SAFE,
            created_by=user_id
        )

        message = f"""
🏗️ **Building Application**

**Task ID:** `{task.task_id}`
**Status:** In Progress

**Process:**
1. ✅ Architect designs system
2. ⏳ Agents implement components
3. ⏳ QA tests
4. ⏳ DevOps deploys

I'll notify you as agents complete each phase.
Use `/status {task.task_id}` to check progress.
"""
        await update.message.reply_text(message, parse_mode='Markdown')

    async def task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /task command"""
        if len(context.args) < 3:
            await update.message.reply_text("Usage: /task <role> <action> <description>")
            return

        role_str = context.args[0]
        action_str = context.args[1]
        description = ' '.join(context.args[2:])

        try:
            agent_role = AgentRole(role_str)
            action_type = ActionType(action_str)
            user_id = f"telegram:{update.effective_user.id}"

            task = await self.coordinator.create_task(
                title=f"Task from {update.effective_user.first_name}",
                description=description,
                assigned_to=agent_role,
                action_type=action_type,
                created_by=user_id
            )

            message = f"""
✅ **Task Created**

**Task ID:** `{task.task_id}`
**Role:** {task.assigned_to.value}
**Action:** {task.action_type.value}
**Status:** {task.status}

{' **⚠️ Pending approval**' if task.requires_approval else '**▶️ Executing now**'}
"""

            # Add approval buttons if needed
            if task.requires_approval:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve:{task.task_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject:{task.task_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(message, parse_mode='Markdown')

        except ValueError as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def approve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /approve command"""
        if not context.args:
            await update.message.reply_text("Usage: /approve <task_id>")
            return

        task_id = context.args[0]
        user_id = f"telegram:{update.effective_user.id}"

        try:
            await self.coordinator.approve_task(task_id, user_id)
            await update.message.reply_text(f"✅ Task `{task_id}` approved and executing", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not context.args:
            await update.message.reply_text("Usage: /status <task_id>")
            return

        task_id = context.args[0]

        try:
            status = await self.coordinator.get_task_status(task_id)

            message = f"""
📊 **Task Status**

**ID:** `{status['task_id']}`
**Title:** {status['title']}
**Status:** {status['status']}
**Assigned To:** {status['assigned_to']}
**Action Type:** {status['action_type']}

**Description:**
{status['description']}
"""

            if status.get('result'):
                result_str = json.dumps(status['result'], indent=2)
                if len(result_str) > 500:
                    result_str = result_str[:500] + "... (truncated)"
                message += f"\n**Result:**\n```json\n{result_str}\n```"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def pending_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pending command"""
        pending = await self.coordinator.get_pending_approvals()

        if not pending:
            await update.message.reply_text("✅ No pending approvals")
            return

        message = f"⏳ **Pending Approvals** ({len(pending)} tasks)\n\n"

        for task in pending[:10]:
            message += f"**{task.task_id}**\n"
            message += f"*{task.title}*\n"
            message += f"{task.description[:100]}...\n"
            message += f"Role: {task.assigned_to.value} | Type: {task.action_type.value}\n\n"

            # Add approval buttons
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve:{task.task_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject:{task.task_id}")
                ]
            ]

        await update.message.reply_text(message, parse_mode='Markdown')

    async def agents_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /agents command"""
        message = "🤖 **Available Agents**\n\nYour autonomous dev team:\n\n"

        for role in AgentRole:
            if role != AgentRole.LEAD:
                name = role.value.replace('_', ' ').title()
                message += f"• **{name}** (`{role.value}`)\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def talk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /talk command"""
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /talk <role> <message>")
            return

        role_str = context.args[0]
        message_text = ' '.join(context.args[1:])

        try:
            agent_role = AgentRole(role_str)
            agent = self.coordinator.agents.get(agent_role)

            if not agent:
                await update.message.reply_text(f"❌ Agent not found: {role_str}")
                return

            # Set conversational mode
            agent.set_mode("conversational")

            # Send typing action
            await update.message.chat.send_action("typing")

            # Get response
            response = await agent.run_conversational(message_text)

            # Format response
            reply = f"""
💬 **{agent_role.value.replace('_', ' ').title()}:**

{response}
"""
            await update.message.reply_text(reply, parse_mode='Markdown')

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def button_callback(self, query: CallbackQueryHandler, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = context.callback_query
        await query.answer()

        data = query.data.split(':')
        action = data[0]
        task_id = data[1] if len(data) > 1 else None

        user_id = f"telegram:{query.from_user.id}"

        if action == 'approve':
            try:
                await self.coordinator.approve_task(task_id, user_id)
                await query.edit_message_text(f"✅ Task `{task_id}` approved and executing")
            except Exception as e:
                await query.edit_message_text(f"❌ Error: {e}")

        elif action == 'reject':
            try:
                task = self.coordinator.tasks.get(task_id)
                if task:
                    task.status = "rejected"
                    await self.coordinator._save_task(task)
                    await query.edit_message_text(f"❌ Task `{task_id}` rejected")
            except Exception as e:
                await query.edit_message_text(f"❌ Error: {e}")

    async def send_message(self, user_id: str, message: str):
        """Send a message to a user (for coordinator notifications)"""
        if user_id.startswith('telegram:'):
            telegram_id = int(user_id.split(':')[1])
            try:
                await self.app.bot.send_message(chat_id=telegram_id, text=message, parse_mode='Markdown')
            except Exception as e:
                print(f"[TelegramBot] Error sending message: {e}")

    async def start(self):
        """Start the bot"""
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        print("[TelegramBot] Started and polling for updates")

    async def stop(self):
        """Stop the bot"""
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()


async def start_telegram_bot(coordinator: AgentCoordinator, token: str):
    """Start the Telegram bot"""
    bot = TelegramAgentBot(coordinator, token)
    await bot.start()
    return bot


if __name__ == '__main__':
    """Test Telegram bot"""
    import os
    from agent_coordinator import create_agent_coordinator

    async def main():
        # Create coordinator
        coordinator = await create_agent_coordinator()

        # Get Telegram token from environment
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            print("Error: TELEGRAM_BOT_TOKEN environment variable not set")
            return

        # Start bot
        bot = await start_telegram_bot(coordinator, token)

        # Keep running
        while True:
            await asyncio.sleep(1)

    asyncio.run(main())
