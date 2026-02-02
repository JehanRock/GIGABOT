"""
Slack channel integration for GigaBot.

Uses Slack Bolt SDK for bot functionality with support for:
- App mentions and DM handling
- Thread support
- Workspace/channel allowlists
- Slash commands
"""

import asyncio
from typing import Any

from loguru import logger

from nanobot.channels.base import BaseChannel
from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import SlackConfig

try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False
    AsyncApp = None
    AsyncSocketModeHandler = None


class SlackChannel(BaseChannel):
    """
    Slack channel implementation using Slack Bolt SDK.
    
    Configuration (via SlackConfig):
    - bot_token: Bot User OAuth Token (xoxb-...)
    - app_token: App-Level Token for Socket Mode (xapp-...)
    - signing_secret: Signing secret for request verification
    - allow_channels: List of allowed channel IDs (empty = all)
    - allow_users: List of allowed user IDs (empty = all)
    """
    
    name = "slack"
    
    def __init__(self, config: SlackConfig, bus: MessageBus):
        """
        Initialize Slack channel.
        
        Args:
            config: Slack configuration.
            bus: Message bus for communication.
        """
        if not SLACK_AVAILABLE:
            raise ImportError(
                "slack-bolt not installed. Install with: pip install slack-bolt"
            )
        
        super().__init__(config, bus)
        
        self.bot_token = config.bot_token
        self.app_token = config.app_token
        self.signing_secret = config.signing_secret
        self.allow_channels = set(config.allow_channels or [])
        self.allow_users = set(config.allow_users or [])
        
        # Initialize Slack app
        self.app = AsyncApp(
            token=self.bot_token,
            signing_secret=self.signing_secret,
        )
        
        self._handler: AsyncSocketModeHandler | None = None
        self._bot_user_id: str = ""
        
        # Track thread contexts for replies
        self._thread_contexts: dict[str, str] = {}
        
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Set up Slack event handlers."""
        
        # Handle app mentions
        @self.app.event("app_mention")
        async def handle_mention(event, say, client):
            await self._handle_message_event(event, say, client)
        
        # Handle direct messages
        @self.app.event("message")
        async def handle_message(event, say, client):
            # Only handle DMs (messages without app mention)
            channel_type = event.get("channel_type", "")
            if channel_type == "im":
                await self._handle_message_event(event, say, client)
        
        # Handle /ask slash command
        @self.app.command("/ask")
        async def handle_ask_command(ack, respond, command, client):
            await ack()  # Acknowledge command
            await self._handle_slash_command(command, respond, client)
        
        # Handle /status slash command
        @self.app.command("/status")
        async def handle_status_command(ack, respond, command, client):
            await ack()
            await respond({
                "response_type": "ephemeral",
                "text": f"GigaBot is running. Channel status: {'connected' if self._running else 'disconnected'}",
            })
    
    def _is_allowed_channel(self, channel_id: str) -> bool:
        """Check if channel is allowed."""
        if not self.allow_channels:
            return True
        return channel_id in self.allow_channels
    
    def _is_allowed_user(self, user_id: str) -> bool:
        """Check if user is allowed."""
        if not self.allow_users:
            return True
        return user_id in self.allow_users
    
    async def _handle_message_event(
        self,
        event: dict[str, Any],
        say,
        client,
    ) -> None:
        """Handle incoming message event."""
        user_id = event.get("user", "")
        channel_id = event.get("channel", "")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        
        # Skip bot messages
        if event.get("bot_id") or user_id == self._bot_user_id:
            return
        
        # Check permissions
        if not self._is_allowed_channel(channel_id):
            return
        if not self._is_allowed_user(user_id):
            return
        
        # Remove bot mention from text
        if self._bot_user_id:
            text = text.replace(f"<@{self._bot_user_id}>", "").strip()
        
        if not text:
            return
        
        # Store thread context for reply routing
        chat_id = f"{channel_id}:{thread_ts}"
        self._thread_contexts[chat_id] = thread_ts
        
        # Use the base class _handle_message method
        await self._handle_message(
            sender_id=user_id,
            chat_id=chat_id,
            content=text,
            metadata={
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "event_ts": event.get("ts"),
                "channel_type": event.get("channel_type", ""),
            }
        )
    
    async def _handle_slash_command(
        self,
        command: dict[str, Any],
        respond,
        client,
    ) -> None:
        """Handle slash command."""
        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")
        text = command.get("text", "")
        
        # Check permissions
        if not self._is_allowed_channel(channel_id):
            await respond({
                "response_type": "ephemeral",
                "text": "This channel is not allowed to use GigaBot.",
            })
            return
        
        if not self._is_allowed_user(user_id):
            await respond({
                "response_type": "ephemeral",
                "text": "You are not allowed to use GigaBot.",
            })
            return
        
        if not text:
            await respond({
                "response_type": "ephemeral",
                "text": "Please provide a question. Usage: /ask <your question>",
            })
            return
        
        # Generate a unique chat_id for slash commands
        chat_id = f"slash:{channel_id}:{command.get('trigger_id', '')}"
        
        # Store response function for later
        # Note: In production, you'd want a more robust way to track this
        self._pending_responds = getattr(self, "_pending_responds", {})
        self._pending_responds[chat_id] = respond
        
        # Use the base class _handle_message method
        await self._handle_message(
            sender_id=user_id,
            chat_id=chat_id,
            content=text,
            metadata={
                "channel_id": channel_id,
                "is_slash_command": True,
                "command": "/ask",
            }
        )
    
    async def start(self) -> None:
        """Start the Slack channel."""
        logger.info("Starting Slack channel")
        self._running = True
        
        # Get bot user ID
        try:
            auth_response = await self.app.client.auth_test()
            self._bot_user_id = auth_response.get("user_id", "")
            logger.info(f"Slack bot authenticated as {auth_response.get('user', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to authenticate Slack bot: {e}")
            self._running = False
            return
        
        # Start Socket Mode handler
        self._handler = AsyncSocketModeHandler(self.app, self.app_token)
        
        try:
            await self._handler.start_async()
        except Exception as e:
            logger.error(f"Slack channel error: {e}")
            self._running = False
    
    async def stop(self) -> None:
        """Stop the Slack channel."""
        logger.info("Stopping Slack channel")
        self._running = False
        
        if self._handler:
            await self._handler.close_async()
            self._handler = None
    
    async def send(self, message: OutboundMessage) -> None:
        """Send a message to Slack."""
        try:
            chat_id = message.chat_id
            
            # Check for pending slash command response
            pending_responds = getattr(self, "_pending_responds", {})
            if chat_id in pending_responds:
                respond = pending_responds.pop(chat_id)
                await respond({
                    "response_type": "in_channel",
                    "text": message.content,
                })
                return
            
            # Parse chat_id: "channel_id:thread_ts"
            if ":" in chat_id:
                parts = chat_id.split(":", 1)
                channel_id = parts[0]
                thread_ts = parts[1] if len(parts) > 1 else None
            else:
                channel_id = chat_id
                thread_ts = None
            
            # Send message
            await self.app.client.chat_postMessage(
                channel=channel_id,
                text=message.content,
                thread_ts=thread_ts,
            )
            
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
    
    async def send_typing(self, chat_id: str) -> None:
        """
        Send a typing indicator.
        
        Note: Slack doesn't have a direct typing indicator API for bots.
        We could send a reaction instead, but this is left as a no-op.
        """
        pass
    
    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running
