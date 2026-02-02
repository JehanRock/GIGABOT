"""
Discord channel integration for GigaBot.

Uses discord.py for bot functionality with support for:
- Slash commands
- Guild/channel allowlists
- DM pairing
- Message reactions
"""

import asyncio
from typing import Any

from loguru import logger

from nanobot.channels.base import BaseChannel
from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import DiscordConfig

try:
    import discord
    from discord import app_commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None
    app_commands = None


class DiscordChannel(BaseChannel):
    """
    Discord channel implementation using discord.py.
    
    Configuration (via DiscordConfig):
    - token: Bot token from Discord Developer Portal
    - application_id: Application ID for slash commands
    - allow_guilds: List of allowed guild IDs (empty = all)
    - allow_channels: List of allowed channel IDs (empty = all)
    - allow_users: List of allowed user IDs (empty = all)
    """
    
    name = "discord"
    
    def __init__(self, config: DiscordConfig, bus: MessageBus):
        """
        Initialize Discord channel.
        
        Args:
            config: Discord configuration.
            bus: Message bus for communication.
        """
        if not DISCORD_AVAILABLE:
            raise ImportError(
                "discord.py not installed. Install with: pip install discord.py"
            )
        
        super().__init__(config, bus)
        
        self.token = config.token
        self.application_id = config.application_id
        self.allow_guilds = set(config.allow_guilds or [])
        self.allow_channels = set(config.allow_channels or [])
        self.allow_users = set(config.allow_users or [])
        
        # Discord client setup
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        intents.guild_messages = True
        
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        
        # Initialize pending interactions dict here, not in start()
        self._pending_interactions: dict[str, discord.Interaction] = {}
        
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Set up Discord event handlers."""
        
        @self.client.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.client.user}")
            
            # Sync slash commands
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
        
        @self.client.event
        async def on_message(message: discord.Message):
            # Ignore own messages
            if message.author == self.client.user:
                return
            
            # Ignore bot messages
            if message.author.bot:
                return
            
            # Check permissions
            if not self._is_allowed_message(message):
                return
            
            # Process message
            await self._process_message(message)
        
        # Register slash command
        @self.tree.command(name="ask", description="Ask GigaBot a question")
        async def ask_command(interaction: discord.Interaction, question: str):
            # Check permissions
            if not self._is_allowed_interaction(interaction):
                await interaction.response.send_message(
                    "You don't have permission to use this bot.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(thinking=True)
            await self._handle_slash_command(interaction, question)
    
    def _is_allowed_message(self, message: discord.Message) -> bool:
        """Check if message sender is allowed."""
        user_id = str(message.author.id)
        
        # Check user allowlist
        if self.allow_users and user_id not in self.allow_users:
            return False
        
        # Check guild allowlist (skip for DMs)
        if message.guild:
            guild_id = str(message.guild.id)
            if self.allow_guilds and guild_id not in self.allow_guilds:
                return False
            
            # Check channel allowlist
            channel_id = str(message.channel.id)
            if self.allow_channels and channel_id not in self.allow_channels:
                return False
        
        return True
    
    def _is_allowed_interaction(self, interaction: discord.Interaction) -> bool:
        """Check if interaction user is allowed."""
        user_id = str(interaction.user.id)
        
        if self.allow_users and user_id not in self.allow_users:
            return False
        
        if interaction.guild:
            guild_id = str(interaction.guild.id)
            if self.allow_guilds and guild_id not in self.allow_guilds:
                return False
            
            # Also check channel allowlist for interactions
            if interaction.channel:
                channel_id = str(interaction.channel.id)
                if self.allow_channels and channel_id not in self.allow_channels:
                    return False
        
        return True
    
    async def _process_message(self, message: discord.Message) -> None:
        """Handle incoming message and publish to bus."""
        # Get chat ID (channel ID or DM ID)
        if message.guild:
            chat_id = f"{message.guild.id}:{message.channel.id}"
        else:
            chat_id = f"dm:{message.author.id}"
        
        # Check for mentions to the bot
        content = message.content
        if self.client.user in message.mentions:
            content = content.replace(f"<@{self.client.user.id}>", "").strip()
        elif message.guild:
            # In guilds, only respond to mentions
            return
        
        if not content:
            return
        
        # Use the base class _handle_message method
        await self._handle_message(
            sender_id=str(message.author.id),
            chat_id=chat_id,
            content=content,
            metadata={
                "username": message.author.name,
                "display_name": message.author.display_name,
                "guild_id": str(message.guild.id) if message.guild else None,
                "channel_id": str(message.channel.id),
                "message_id": str(message.id),
            }
        )
    
    async def _handle_slash_command(
        self, 
        interaction: discord.Interaction, 
        question: str
    ) -> None:
        """Handle slash command."""
        # Get chat ID
        if interaction.guild:
            chat_id = f"{interaction.guild.id}:{interaction.channel.id}"
        else:
            chat_id = f"dm:{interaction.user.id}"
        
        # Store interaction for response
        self._pending_interactions[chat_id] = interaction
        
        # Use the base class _handle_message method
        await self._handle_message(
            sender_id=str(interaction.user.id),
            chat_id=chat_id,
            content=question,
            metadata={
                "username": interaction.user.name,
                "display_name": interaction.user.display_name,
                "is_slash_command": True,
                "interaction_id": str(interaction.id),
            }
        )
    
    async def start(self) -> None:
        """Start the Discord bot."""
        logger.info("Starting Discord channel")
        self._running = True
        
        try:
            await self.client.start(self.token)
        except Exception as e:
            logger.error(f"Discord bot error: {e}")
            self._running = False
    
    async def stop(self) -> None:
        """Stop the Discord bot."""
        logger.info("Stopping Discord channel")
        self._running = False
        await self.client.close()
    
    async def send(self, message: OutboundMessage) -> None:
        """Send a message to Discord."""
        try:
            chat_id = message.chat_id
            
            # Check for pending slash command interaction
            if chat_id in self._pending_interactions:
                interaction = self._pending_interactions.pop(chat_id)
                await interaction.followup.send(message.content)
                return
            
            # Parse chat_id
            if chat_id.startswith("dm:"):
                user_id = int(chat_id[3:])
                user = await self.client.fetch_user(user_id)
                await user.send(message.content)
            else:
                # Guild message: "guild_id:channel_id"
                parts = chat_id.split(":")
                if len(parts) >= 2:
                    channel_id = int(parts[-1])
                    channel = await self.client.fetch_channel(channel_id)
                    await channel.send(message.content)
                    
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
    
    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running and self.client.is_ready()
