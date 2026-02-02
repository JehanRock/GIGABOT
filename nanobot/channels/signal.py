"""
Signal channel integration for GigaBot.

Uses signal-cli daemon for message handling with support for:
- SSE stream for real-time messages
- E2EE (built into Signal protocol)
- Phone number allowlists
"""

import asyncio
import json
import subprocess
from typing import Any

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

from loguru import logger

from nanobot.channels.base import BaseChannel
from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import SignalConfig


class SignalChannel(BaseChannel):
    """
    Signal channel implementation using signal-cli.
    
    Requires signal-cli to be installed and configured:
    - Run `signal-cli link` to link the device
    - Run `signal-cli -a +PHONE daemon --json-rpc` for JSON-RPC mode
    
    Configuration (via SignalConfig):
    - phone_number: Your Signal phone number (e.g., +1234567890)
    - signal_cli_path: Path to signal-cli binary
    - config_path: Path to signal-cli config directory
    - allow_from: List of allowed phone numbers (empty = all)
    """
    
    name = "signal"
    
    def __init__(self, config: SignalConfig, bus: MessageBus):
        """
        Initialize Signal channel.
        
        Args:
            config: Signal configuration.
            bus: Message bus for communication.
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx not installed. Install with: pip install httpx"
            )
        
        super().__init__(config, bus)
        
        self.phone_number = config.phone_number
        self.signal_cli_path = config.signal_cli_path
        self.config_path = config.config_path
        self.allow_from = set(config.allow_from or [])
        
        # Default daemon URL
        self.daemon_url = "http://localhost:8080"
        
        self._daemon_process: subprocess.Popen | None = None
        self._client = httpx.AsyncClient(timeout=30.0)
    
    def is_allowed(self, sender_id: str) -> bool:
        """Check if phone number is allowed."""
        if not self.allow_from:
            return True
        return sender_id in self.allow_from
    
    async def start(self) -> None:
        """Start the Signal channel."""
        logger.info(f"Starting Signal channel for {self.phone_number}")
        self._running = True
        
        # Start daemon if not running
        await self._ensure_daemon()
        
        # Start SSE listener
        asyncio.create_task(self._listen_sse())
    
    async def _ensure_daemon(self) -> None:
        """Ensure signal-cli daemon is running."""
        try:
            # Check if daemon is already running
            response = await self._client.get(f"{self.daemon_url}/v1/about")
            if response.status_code == 200:
                logger.info("Signal daemon already running")
                return
        except Exception:
            pass
        
        # Start daemon
        logger.info("Starting signal-cli daemon...")
        cmd = [
            self.signal_cli_path,
            "-a", self.phone_number,
        ]
        
        if self.config_path:
            cmd.extend(["--config", self.config_path])
        
        cmd.extend(["daemon", "--json-rpc", "--receive-mode", "on-connection"])
        
        try:
            self._daemon_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Give it time to start
            await asyncio.sleep(2)
            logger.info("Signal daemon started")
        except Exception as e:
            logger.error(f"Failed to start signal-cli daemon: {e}")
    
    async def _listen_sse(self) -> None:
        """Listen for messages via SSE stream."""
        reconnect_delay = 1
        max_delay = 60
        
        while self._running:
            try:
                async with self._client.stream(
                    "GET",
                    f"{self.daemon_url}/v1/receive/{self.phone_number}",
                    timeout=None,
                ) as response:
                    reconnect_delay = 1  # Reset on successful connection
                    
                    async for line in response.aiter_lines():
                        if not self._running:
                            break
                        
                        if not line or not line.startswith("data:"):
                            continue
                        
                        try:
                            data = json.loads(line[5:].strip())
                            await self._process_message(data)
                        except json.JSONDecodeError:
                            continue
                        
            except Exception as e:
                if self._running:
                    logger.warning(f"Signal SSE connection error: {e}")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_delay)
    
    async def _process_message(self, data: dict[str, Any]) -> None:
        """Handle incoming Signal message."""
        # Extract envelope
        envelope = data.get("envelope", {})
        source = envelope.get("source", "")
        
        # Check allowlist
        if not self.is_allowed(source):
            return
        
        # Get message content
        data_message = envelope.get("dataMessage", {})
        message_text = data_message.get("message", "")
        
        if not message_text:
            # Could be a receipt, reaction, etc.
            return
        
        # Handle group messages
        group_info = data_message.get("groupInfo", {})
        group_id = group_info.get("groupId", "")
        
        chat_id = group_id if group_id else source
        
        # Use the base class _handle_message method
        await self._handle_message(
            sender_id=source,
            chat_id=chat_id,
            content=message_text,
            metadata={
                "timestamp": envelope.get("timestamp"),
                "server_timestamp": envelope.get("serverReceivedTimestamp"),
                "is_group": bool(group_id),
                "group_id": group_id,
            }
        )
    
    async def stop(self) -> None:
        """Stop the Signal channel."""
        logger.info("Stopping Signal channel")
        self._running = False
        
        if self._daemon_process:
            self._daemon_process.terminate()
            self._daemon_process = None
        
        await self._client.aclose()
    
    async def send(self, message: OutboundMessage) -> None:
        """Send a message via Signal."""
        try:
            chat_id = message.chat_id
            
            # Determine if group or individual
            if chat_id.startswith("+"):
                # Individual message
                payload = {
                    "message": message.content,
                    "number": self.phone_number,
                    "recipients": [chat_id],
                }
            else:
                # Group message
                payload = {
                    "message": message.content,
                    "number": self.phone_number,
                    "group-id": chat_id,
                }
            
            await self._client.post(
                f"{self.daemon_url}/v2/send",
                json=payload,
            )
            
        except Exception as e:
            logger.error(f"Failed to send Signal message: {e}")
    
    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running


class SignalCLI:
    """
    Utility class for signal-cli operations.
    
    Provides methods for:
    - Linking new devices
    - Verifying phone numbers
    - Managing groups
    """
    
    def __init__(self, cli_path: str = "signal-cli", config_path: str = ""):
        self.cli_path = cli_path
        self.config_path = config_path
    
    def _build_cmd(self, *args: str) -> list[str]:
        """Build signal-cli command."""
        cmd = [self.cli_path]
        if self.config_path:
            cmd.extend(["--config", self.config_path])
        cmd.extend(args)
        return cmd
    
    async def link(self, device_name: str = "GigaBot") -> str:
        """
        Generate QR code for linking.
        
        Returns:
            URI for QR code generation.
        """
        cmd = self._build_cmd("link", "-n", device_name)
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # The URI is printed to stdout
        for line in result.stdout.split("\n"):
            if line.startswith("sgnl://"):
                return line
        
        raise RuntimeError(f"Failed to generate link: {result.stderr}")
    
    async def verify(self, phone: str, code: str) -> bool:
        """Verify phone number with code."""
        cmd = self._build_cmd("verify", "-a", phone, code)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    
    async def list_groups(self, phone: str) -> list[dict[str, Any]]:
        """List groups for a phone number."""
        cmd = self._build_cmd("-a", phone, "listGroups", "-d")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return []
        
        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
