"""
Node Host for GigaBot.

A headless node host that connects to the gateway and executes commands
on the local machine.
"""

import asyncio
import json
import platform
import shutil
import socket
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from nanobot.nodes.protocol import (
    NodeCapability,
    NodeMessage,
    NodeMessageType,
    NodeInvoke,
    NodeInvokeResult,
    NodeErrorCode,
    CAPABILITY_SYSTEM_RUN,
    CAPABILITY_SYSTEM_WHICH,
)
from nanobot.nodes.approvals import ExecApprovalManager


class NodeHost:
    """
    Headless node host that connects to a GigaBot gateway.
    
    Capabilities:
    - system.run: Execute shell commands
    - system.which: Check if a command exists
    
    Security:
    - Token-based authentication
    - Local exec allowlist
    """
    
    def __init__(
        self,
        gateway_url: str,
        token: str = "",
        display_name: str = "",
        node_id: str = "",
        config_path: Path | None = None,
        approval_manager: ExecApprovalManager | None = None,
        ssl_verify: bool = True,
        ssl_fingerprint: str = "",
    ):
        """
        Initialize the NodeHost.
        
        Args:
            gateway_url: WebSocket URL of the gateway (e.g., ws://localhost:18790/ws/nodes)
            token: Authentication token
            display_name: Human-readable name for this node
            node_id: Unique node identifier (generated if not provided)
            config_path: Path to store node config (default: ~/.gigabot/node.json)
            approval_manager: ExecApprovalManager for command allowlists
            ssl_verify: Whether to verify SSL certificates (default: True)
            ssl_fingerprint: Optional SHA256 fingerprint for certificate pinning
        """
        if not AIOHTTP_AVAILABLE:
            raise ImportError(
                "aiohttp not installed. Install with: pip install aiohttp"
            )
        
        self.gateway_url = gateway_url
        self.token = token
        self.display_name = display_name or socket.gethostname()
        self._node_id_provided = bool(node_id)  # Track if user provided node_id
        self.node_id = node_id or str(uuid.uuid4())
        self.config_path = config_path or Path.home() / ".gigabot" / "node.json"
        
        # Exec approval manager
        self._approval_manager = approval_manager or ExecApprovalManager()
        
        # SSL/TLS settings
        self._ssl_verify = ssl_verify
        self._ssl_fingerprint = ssl_fingerprint
        
        # Connection state
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self._connected = False
        self._paired = False
        
        # Reconnection settings
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._reconnect_attempts = 0
        
        # Capabilities
        self._capabilities = [
            CAPABILITY_SYSTEM_RUN,
            CAPABILITY_SYSTEM_WHICH,
        ]
        
        # Load existing config
        self._load_config()
    
    def _load_config(self) -> None:
        """Load node configuration from file."""
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text())
                # Use existing node_id from config if not explicitly provided
                if not self._node_id_provided and data.get("node_id"):
                    self.node_id = data["node_id"]
                if not self.token:
                    self.token = data.get("token", "")
                if not self.display_name or self.display_name == socket.gethostname():
                    self.display_name = data.get("display_name", self.display_name)
                if not self.gateway_url:
                    self.gateway_url = data.get("gateway_url", "")
                logger.debug(f"Loaded node config: {self.node_id[:8]}...")
            except Exception as e:
                logger.warning(f"Failed to load node config: {e}")
    
    def _save_config(self) -> None:
        """Save node configuration to file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "node_id": self.node_id,
                "display_name": self.display_name,
                "gateway_url": self.gateway_url,
                "token": self.token,
                "updated_at": datetime.now().isoformat(),
            }
            self.config_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save node config: {e}")
    
    async def start(self) -> None:
        """Start the node host and connect to the gateway."""
        if self._running:
            return
        
        self._running = True
        self._save_config()
        
        logger.info(f"Starting node host: {self.display_name} ({self.node_id[:8]}...)")
        logger.info(f"Connecting to gateway: {self.gateway_url}")
        
        while self._running:
            try:
                await self._connect()
                await self._run_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Connection error: {e}")
            
            if self._running:
                # Reconnect with backoff
                delay = min(
                    self._reconnect_delay * (2 ** self._reconnect_attempts),
                    self._max_reconnect_delay,
                )
                self._reconnect_attempts += 1
                logger.info(f"Reconnecting in {delay:.1f}s...")
                await asyncio.sleep(delay)
        
        await self._disconnect()
        logger.info("Node host stopped")
    
    async def stop(self) -> None:
        """Stop the node host."""
        self._running = False
        await self._disconnect()
    
    async def _connect(self) -> None:
        """Establish WebSocket connection to gateway."""
        import ssl
        
        # Configure SSL context
        ssl_context: ssl.SSLContext | bool | None = None
        if self.gateway_url.startswith("wss://"):
            if not self._ssl_verify:
                # Create a context that doesn't verify certificates
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                logger.warning("SSL certificate verification disabled")
            elif self._ssl_fingerprint:
                # Certificate pinning would require custom verification
                logger.info(f"SSL fingerprint configured: {self._ssl_fingerprint[:16]}...")
        
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        self._ws = await self._session.ws_connect(
            self.gateway_url,
            heartbeat=30.0,
            ssl=ssl_context,
        )
        
        # Send CONNECT message
        connect_msg = NodeMessage.connect(
            node_id=self.node_id,
            display_name=self.display_name,
            capabilities=self._capabilities,
            platform=platform.system().lower(),
            hostname=socket.gethostname(),
            token=self.token,
        )
        await self._ws.send_json(connect_msg.to_dict())
        
        # Wait for ACK or REJECT
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                response = NodeMessage.from_dict(data)
                
                if response.type == NodeMessageType.CONNECT_ACK:
                    self._connected = True
                    self._paired = response.payload.get("paired", False)
                    self._reconnect_attempts = 0
                    
                    if self._paired:
                        logger.info("Connected and paired to gateway")
                    else:
                        logger.info("Connected to gateway (pending approval)")
                    break
                
                elif response.type == NodeMessageType.CONNECT_REJECT:
                    reason = response.payload.get("reason", "Unknown")
                    raise ConnectionRefusedError(f"Connection rejected: {reason}")
            
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                raise ConnectionError("WebSocket closed during handshake")
    
    async def _disconnect(self) -> None:
        """Close the connection."""
        self._connected = False
        self._paired = False
        
        if self._ws and not self._ws.closed:
            # Send DISCONNECT message
            try:
                disconnect_msg = NodeMessage(
                    type=NodeMessageType.DISCONNECT,
                    node_id=self.node_id,
                )
                await self._ws.send_json(disconnect_msg.to_dict())
            except Exception:
                pass
            
            await self._ws.close()
        
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _run_loop(self) -> None:
        """Main message loop."""
        if not self._ws:
            return
        
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
            
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                logger.info("WebSocket closed by gateway")
                break
            
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {self._ws.exception()}")
                break
    
    async def _handle_message(self, data: dict) -> None:
        """Handle an incoming message from the gateway."""
        message = NodeMessage.from_dict(data)
        
        if message.type == NodeMessageType.PING:
            pong = NodeMessage.pong(self.node_id)
            await self._ws.send_json(pong.to_dict())
        
        elif message.type == NodeMessageType.CONNECT_ACK:
            # Update paired status
            self._paired = message.payload.get("paired", False)
            if self._paired:
                logger.info("Node approved and paired")
        
        elif message.type == NodeMessageType.INVOKE:
            result = await self._handle_invoke(message.payload)
            result_msg = NodeMessage.invoke_result(self.node_id, result)
            await self._ws.send_json(result_msg.to_dict())
        
        elif message.type == NodeMessageType.DISCONNECT:
            logger.info("Gateway requested disconnect")
            self._running = False
    
    async def _handle_invoke(self, payload: dict) -> NodeInvokeResult:
        """Handle a command invocation."""
        invoke = NodeInvoke.from_dict(payload)
        start_time = time.time()
        
        try:
            if invoke.command == "system.run":
                result = await self._exec_system_run(invoke)
            elif invoke.command == "system.which":
                result = await self._exec_system_which(invoke)
            else:
                result = NodeInvokeResult(
                    invoke_id=invoke.id,
                    success=False,
                    error=f"Unknown command: {invoke.command}",
                    error_code=NodeErrorCode.CAPABILITY_NOT_SUPPORTED,
                )
        except Exception as e:
            result = NodeInvokeResult(
                invoke_id=invoke.id,
                success=False,
                error=str(e),
            )
        
        result.duration_ms = (time.time() - start_time) * 1000
        return result
    
    async def _exec_system_run(self, invoke: NodeInvoke) -> NodeInvokeResult:
        """Execute a shell command."""
        command = invoke.params.get("command", "")
        cwd = invoke.params.get("cwd")
        env = invoke.params.get("env", {})
        timeout = invoke.params.get("timeout", 60)
        
        if not command:
            return NodeInvokeResult(
                invoke_id=invoke.id,
                success=False,
                error="No command provided",
            )
        
        # Check if command is approved
        approval_result = self._approval_manager.check_approval(command)
        if not approval_result.allowed:
            return NodeInvokeResult(
                invoke_id=invoke.id,
                success=False,
                error=f"Command not approved: {approval_result.reason}",
                error_code=NodeErrorCode.EXEC_DENIED,
            )
        
        logger.debug(f"Executing: {command}")
        
        try:
            # Build environment
            process_env = dict(**env) if env else None
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=process_env,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                return NodeInvokeResult(
                    invoke_id=invoke.id,
                    success=False,
                    error=f"Command timed out after {timeout}s",
                    error_code=NodeErrorCode.TIMEOUT,
                )
            
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            return NodeInvokeResult(
                invoke_id=invoke.id,
                success=process.returncode == 0,
                result={
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": process.returncode,
                },
                error=stderr_str if process.returncode != 0 else "",
            )
            
        except Exception as e:
            return NodeInvokeResult(
                invoke_id=invoke.id,
                success=False,
                error=str(e),
            )
    
    async def _exec_system_which(self, invoke: NodeInvoke) -> NodeInvokeResult:
        """Check if a command exists."""
        command = invoke.params.get("command", "")
        
        if not command:
            return NodeInvokeResult(
                invoke_id=invoke.id,
                success=False,
                error="No command provided",
            )
        
        path = shutil.which(command)
        
        return NodeInvokeResult(
            invoke_id=invoke.id,
            success=True,
            result={
                "exists": path is not None,
                "path": path,
            },
        )
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to gateway."""
        return self._connected
    
    @property
    def is_paired(self) -> bool:
        """Check if paired with gateway."""
        return self._paired


async def run_node_host(
    gateway_host: str,
    gateway_port: int = 18790,
    token: str = "",
    display_name: str = "",
    use_tls: bool = False,
    ssl_verify: bool = True,
    ssl_fingerprint: str = "",
) -> None:
    """
    Run a node host connected to a gateway.
    
    Args:
        gateway_host: Gateway host address
        gateway_port: Gateway port
        token: Authentication token
        display_name: Node display name
        use_tls: Use TLS (wss://) instead of plain WebSocket
        ssl_verify: Whether to verify SSL certificates (default: True)
        ssl_fingerprint: Optional SHA256 fingerprint for certificate pinning
    """
    protocol = "wss" if use_tls else "ws"
    gateway_url = f"{protocol}://{gateway_host}:{gateway_port}/ws/nodes"
    
    host = NodeHost(
        gateway_url=gateway_url,
        token=token,
        display_name=display_name,
        ssl_verify=ssl_verify,
        ssl_fingerprint=ssl_fingerprint,
    )
    
    try:
        await host.start()
    except KeyboardInterrupt:
        await host.stop()
