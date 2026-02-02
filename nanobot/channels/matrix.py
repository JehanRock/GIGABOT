"""
Matrix channel integration for GigaBot.

Uses matrix-nio for bot functionality with support for:
- Access token or password authentication
- Optional E2EE (end-to-end encryption)
- Room/space allowlists
"""

import asyncio
import re
from typing import Any

from loguru import logger

from nanobot.channels.base import BaseChannel
from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import MatrixConfig

try:
    from nio import (
        AsyncClient,
        AsyncClientConfig,
        LoginResponse,
        RoomMessageText,
        InviteMemberEvent,
        SyncError,
    )
    NIO_AVAILABLE = True
except ImportError:
    NIO_AVAILABLE = False
    AsyncClient = None


class MatrixChannel(BaseChannel):
    """
    Matrix channel implementation using matrix-nio.
    
    Configuration (via MatrixConfig):
    - homeserver: Matrix homeserver URL (e.g., https://matrix.org)
    - user_id: Bot user ID (e.g., @gigabot:matrix.org)
    - access_token: Access token (preferred) or use password
    - password: Password for login (if no access_token)
    - device_id: Device ID for E2EE session persistence
    - enable_encryption: Enable E2EE support
    - allow_rooms: List of allowed room IDs (empty = all)
    """
    
    name = "matrix"
    
    def __init__(self, config: MatrixConfig, bus: MessageBus):
        """
        Initialize Matrix channel.
        
        Args:
            config: Matrix configuration.
            bus: Message bus for communication.
        """
        if not NIO_AVAILABLE:
            raise ImportError(
                "matrix-nio not installed. Install with: pip install matrix-nio"
            )
        
        super().__init__(config, bus)
        
        self.homeserver = config.homeserver
        self.user_id = config.user_id
        self.access_token = config.access_token
        self.password = config.password
        self.device_id = config.device_id
        self.enable_encryption = config.enable_encryption
        self.allow_rooms = set(config.allow_rooms or [])
        self.auto_join = True  # Default to auto-join
        self.store_path = ""  # Default no persistence
        
        self._client: AsyncClient | None = None
    
    def is_allowed(self, sender_id: str) -> bool:
        """
        Check if sender is allowed.
        
        For Matrix, we check the room allowlist in _is_room_allowed instead.
        """
        return True
    
    def _is_room_allowed(self, room_id: str) -> bool:
        """Check if room is allowed."""
        if not self.allow_rooms:
            return True
        return room_id in self.allow_rooms
    
    async def _create_client(self) -> AsyncClient:
        """Create and configure the Matrix client."""
        config = AsyncClientConfig(
            encryption_enabled=self.enable_encryption,
            store_sync_tokens=True,
        )
        
        client = AsyncClient(
            self.homeserver,
            self.user_id,
            device_id=self.device_id or None,
            store_path=self.store_path or None,
            config=config,
        )
        
        return client
    
    async def _login(self) -> bool:
        """Login to the Matrix homeserver."""
        if self.access_token:
            # Use access token
            self._client.access_token = self.access_token
            self._client.user_id = self.user_id
            
            # Verify token works
            response = await self._client.whoami()
            if hasattr(response, "user_id"):
                logger.info(f"Matrix logged in as {response.user_id}")
                return True
            else:
                logger.error("Matrix token validation failed")
                return False
        
        elif self.password:
            # Login with password
            response = await self._client.login(self.password, device_name="GigaBot")
            
            if isinstance(response, LoginResponse):
                logger.info(f"Matrix logged in as {response.user_id}")
                # Store access token for future use
                self.access_token = response.access_token
                self.device_id = response.device_id
                return True
            else:
                logger.error(f"Matrix login failed: {response}")
                return False
        
        else:
            logger.error("No access_token or password provided for Matrix")
            return False
    
    def _setup_callbacks(self) -> None:
        """Set up event callbacks."""
        
        async def message_callback(room, event: RoomMessageText):
            """Handle incoming text messages."""
            # Ignore own messages
            if event.sender == self._client.user_id:
                return
            
            # Check room allowlist
            if not self._is_room_allowed(room.room_id):
                return
            
            await self._process_message(room, event)
        
        async def invite_callback(room, event: InviteMemberEvent):
            """Handle room invites."""
            if not self.auto_join:
                return
            
            # Check room allowlist
            if self.allow_rooms and room.room_id not in self.allow_rooms:
                logger.info(f"Declining invite to {room.room_id} (not in allowlist)")
                return
            
            logger.info(f"Accepting invite to {room.room_id}")
            await self._client.join(room.room_id)
        
        self._client.add_event_callback(message_callback, RoomMessageText)
        self._client.add_event_callback(invite_callback, InviteMemberEvent)
    
    async def _process_message(self, room, event: RoomMessageText) -> None:
        """Handle incoming Matrix message."""
        # Get display name
        display_name = room.user_name(event.sender) or event.sender
        
        # Use the base class _handle_message method
        await self._handle_message(
            sender_id=event.sender,
            chat_id=room.room_id,
            content=event.body,
            metadata={
                "display_name": display_name,
                "room_name": room.display_name,
                "event_id": event.event_id,
                "server_timestamp": event.server_timestamp,
                "is_encrypted": False,  # TODO: Track encryption status
            }
        )
    
    async def start(self) -> None:
        """Start the Matrix channel."""
        logger.info(f"Starting Matrix channel for {self.user_id}")
        
        self._client = await self._create_client()
        
        if not await self._login():
            logger.error("Matrix login failed, not starting")
            return
        
        self._running = True
        self._setup_callbacks()
        
        # Start sync loop
        asyncio.create_task(self._sync_loop())
    
    async def _sync_loop(self) -> None:
        """Main sync loop for receiving events."""
        while self._running:
            try:
                sync_response = await self._client.sync(
                    timeout=30000,  # 30 seconds
                    full_state=False,
                )
                
                if isinstance(sync_response, SyncError):
                    logger.error(f"Matrix sync error: {sync_response}")
                    await asyncio.sleep(5)
                    
            except Exception as e:
                if self._running:
                    logger.error(f"Matrix sync exception: {e}")
                    await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """Stop the Matrix channel."""
        logger.info("Stopping Matrix channel")
        self._running = False
        
        if self._client:
            await self._client.close()
            self._client = None
    
    async def send(self, message: OutboundMessage) -> None:
        """Send a message to Matrix."""
        if not self._client:
            return
        
        try:
            room_id = message.chat_id
            
            # Format message (support markdown)
            content = {
                "msgtype": "m.text",
                "body": message.content,
            }
            
            # Check for markdown
            if any(c in message.content for c in ["**", "*", "`", "```", "[", "#"]):
                # Add formatted body
                content["format"] = "org.matrix.custom.html"
                content["formatted_body"] = self._markdown_to_html(message.content)
            
            await self._client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
            )
            
        except Exception as e:
            logger.error(f"Failed to send Matrix message: {e}")
    
    def _markdown_to_html(self, text: str) -> str:
        """Convert simple markdown to HTML."""
        # Code blocks
        text = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", text, flags=re.DOTALL)
        
        # Inline code
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        
        # Bold
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        
        # Italic
        text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
        
        # Links
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        
        # Line breaks
        text = text.replace("\n", "<br/>")
        
        return text
    
    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running


class MatrixUtils:
    """
    Utility class for Matrix operations.
    
    Provides methods for:
    - Creating rooms
    - Inviting users
    - Managing room settings
    """
    
    def __init__(self, client: AsyncClient):
        self.client = client
    
    async def create_room(
        self,
        name: str,
        topic: str = "",
        invite: list[str] | None = None,
        is_direct: bool = False,
    ) -> str | None:
        """
        Create a new room.
        
        Returns:
            Room ID if successful, None otherwise.
        """
        response = await self.client.room_create(
            name=name,
            topic=topic,
            invite=invite or [],
            is_direct=is_direct,
        )
        
        if hasattr(response, "room_id"):
            return response.room_id
        return None
    
    async def invite_user(self, room_id: str, user_id: str) -> bool:
        """Invite a user to a room."""
        response = await self.client.room_invite(room_id, user_id)
        return not hasattr(response, "status_code") or response.status_code == 200
    
    async def leave_room(self, room_id: str) -> bool:
        """Leave a room."""
        response = await self.client.room_leave(room_id)
        return not hasattr(response, "status_code") or response.status_code == 200
    
    async def get_joined_rooms(self) -> list[str]:
        """Get list of joined room IDs."""
        response = await self.client.joined_rooms()
        if hasattr(response, "rooms"):
            return response.rooms
        return []
