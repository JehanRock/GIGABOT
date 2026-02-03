"""
Node Manager for GigaBot.

Gateway-side management of connected nodes, including:
- Node registration and pairing workflow
- Connection tracking
- Command invocation routing
- Health monitoring
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Awaitable

from aiohttp import web
from loguru import logger

from nanobot.nodes.protocol import (
    NodeStatus,
    NodeCapability,
    NodeInfo,
    NodeInvoke,
    NodeInvokeResult,
    NodeMessage,
    NodeMessageType,
    NodeErrorCode,
)


class NodeConnection:
    """Represents an active WebSocket connection to a node."""
    
    def __init__(
        self,
        ws: web.WebSocketResponse,
        node_id: str,
        ip_address: str = "",
    ):
        self.ws = ws
        self.node_id = node_id
        self.ip_address = ip_address
        self.connected_at = datetime.now()
        self.last_ping = datetime.now()
        self._pending_invokes: dict[str, asyncio.Future] = {}
    
    async def send(self, message: NodeMessage) -> None:
        """Send a message to the node."""
        if not self.ws.closed:
            await self.ws.send_json(message.to_dict())
    
    async def invoke(
        self,
        invoke: NodeInvoke,
        timeout: float | None = None,
    ) -> NodeInvokeResult:
        """
        Send an invoke command and wait for the result.
        
        Args:
            invoke: The invoke command to send
            timeout: Timeout in seconds (defaults to invoke.timeout_ms / 1000)
        
        Returns:
            NodeInvokeResult with the command result
        """
        if timeout is None:
            timeout = invoke.timeout_ms / 1000
        
        # Create future for the result
        future: asyncio.Future[NodeInvokeResult] = asyncio.Future()
        self._pending_invokes[invoke.id] = future
        
        try:
            # Send the invoke message
            message = NodeMessage.invoke(self.node_id, invoke)
            await self.send(message)
            
            # Wait for result with timeout
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            return NodeInvokeResult(
                invoke_id=invoke.id,
                success=False,
                error=f"Invoke timed out after {timeout}s",
                error_code=NodeErrorCode.TIMEOUT,
            )
        finally:
            self._pending_invokes.pop(invoke.id, None)
    
    def handle_invoke_result(self, result: NodeInvokeResult) -> None:
        """Handle an incoming invoke result."""
        future = self._pending_invokes.get(result.invoke_id)
        if future and not future.done():
            future.set_result(result)
    
    def close_pending_invokes(self) -> None:
        """Cancel all pending invokes on disconnect."""
        for invoke_id, future in self._pending_invokes.items():
            if not future.done():
                future.set_exception(
                    ConnectionError(f"Node disconnected during invoke {invoke_id}")
                )
        self._pending_invokes.clear()


class NodeManager:
    """
    Manages nodes connected to the gateway.
    
    Handles:
    - Node registration and pairing
    - Connection tracking
    - Command invocation routing
    - Persistence of node registry
    """
    
    def __init__(
        self,
        storage_path: Path | None = None,
        auth_token: str = "",
        auto_approve: bool = False,
        ping_interval: float = 30.0,
    ):
        """
        Initialize the NodeManager.
        
        Args:
            storage_path: Path to store node registry (default: ~/.gigabot/nodes.json)
            auth_token: Token required for node authentication
            auto_approve: If True, automatically approve new nodes
            ping_interval: Interval in seconds for health check pings
        """
        self.storage_path = storage_path or Path.home() / ".gigabot" / "nodes.json"
        self.auth_token = auth_token
        self.auto_approve = auto_approve
        self.ping_interval = ping_interval
        
        # Node registry (persisted)
        self._nodes: dict[str, NodeInfo] = {}
        
        # Active connections (not persisted)
        self._connections: dict[str, NodeConnection] = {}
        
        # Callbacks
        self._on_node_connected: list[Callable[[NodeInfo], Awaitable[None]]] = []
        self._on_node_disconnected: list[Callable[[NodeInfo], Awaitable[None]]] = []
        self._on_node_pending: list[Callable[[NodeInfo], Awaitable[None]]] = []
        
        # Background tasks
        self._ping_task: asyncio.Task | None = None
        self._running = False
        
        # Load existing nodes
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load node registry from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                for node_data in data.get("nodes", []):
                    node = NodeInfo.from_dict(node_data)
                    # Reset connection status on load
                    if node.status == NodeStatus.CONNECTED:
                        node.status = NodeStatus.PAIRED
                    self._nodes[node.id] = node
                logger.info(f"Loaded {len(self._nodes)} nodes from registry")
            except Exception as e:
                logger.warning(f"Failed to load node registry: {e}")
    
    def _save_registry(self) -> None:
        """Save node registry to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "nodes": [node.to_dict() for node in self._nodes.values()],
                "updated_at": datetime.now().isoformat(),
            }
            self.storage_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save node registry: {e}")
    
    async def start(self) -> None:
        """Start the node manager background tasks."""
        if self._running:
            return
        
        self._running = True
        self._ping_task = asyncio.create_task(self._ping_loop())
        logger.info("NodeManager started")
    
    async def stop(self) -> None:
        """Stop the node manager and disconnect all nodes."""
        self._running = False
        
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all nodes
        for node_id in list(self._connections.keys()):
            await self.disconnect_node(node_id)
        
        self._save_registry()
        logger.info("NodeManager stopped")
    
    async def _ping_loop(self) -> None:
        """Background task to ping connected nodes."""
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)
                
                for node_id, conn in list(self._connections.items()):
                    try:
                        await conn.send(NodeMessage.ping(node_id))
                    except Exception as e:
                        logger.warning(f"Failed to ping node {node_id}: {e}")
                        await self.disconnect_node(node_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
    
    async def handle_connection(
        self,
        ws: web.WebSocketResponse,
        ip_address: str = "",
    ) -> None:
        """
        Handle a new WebSocket connection from a node.
        
        Args:
            ws: The WebSocket connection
            ip_address: IP address of the connecting node
        """
        node_id: str | None = None
        
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        message = NodeMessage.from_dict(data)
                        
                        if message.type == NodeMessageType.CONNECT:
                            node_id = await self._handle_connect(ws, message, ip_address)
                            if not node_id:
                                break
                        
                        elif message.type == NodeMessageType.PONG:
                            if node_id and node_id in self._connections:
                                self._connections[node_id].last_ping = datetime.now()
                        
                        elif message.type == NodeMessageType.INVOKE_RESULT:
                            if node_id and node_id in self._connections:
                                result = NodeInvokeResult.from_dict(message.payload)
                                self._connections[node_id].handle_invoke_result(result)
                        
                        elif message.type == NodeMessageType.CAPABILITIES:
                            if node_id and node_id in self._nodes:
                                caps = [
                                    NodeCapability.from_dict(c)
                                    for c in message.payload.get("capabilities", [])
                                ]
                                self._nodes[node_id].capabilities = caps
                                self._save_registry()
                        
                        elif message.type == NodeMessageType.DISCONNECT:
                            break
                            
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON from node")
                    except Exception as e:
                        logger.error(f"Error handling node message: {e}")
                
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
        
        finally:
            if node_id:
                await self.disconnect_node(node_id)
    
    async def _handle_connect(
        self,
        ws: web.WebSocketResponse,
        message: NodeMessage,
        ip_address: str,
    ) -> str | None:
        """Handle a CONNECT message from a node."""
        payload = message.payload
        node_id = message.node_id
        token = payload.get("token", "")
        
        # Validate token if required
        if self.auth_token and token != self.auth_token:
            reject = NodeMessage.connect_reject(node_id, "Invalid authentication token")
            await ws.send_json(reject.to_dict())
            logger.warning(f"Node {node_id} rejected: invalid token")
            return None
        
        # Get or create node info
        if node_id in self._nodes:
            node = self._nodes[node_id]
        else:
            # New node
            node = NodeInfo(
                id=node_id,
                display_name=payload.get("display_name", node_id[:8]),
                status=NodeStatus.PENDING,
                capabilities=[
                    NodeCapability.from_dict(c)
                    for c in payload.get("capabilities", [])
                ],
                ip_address=ip_address,
                hostname=payload.get("hostname", ""),
                platform=payload.get("platform", ""),
            )
            self._nodes[node_id] = node
        
        # Update node info
        node.ip_address = ip_address
        node.hostname = payload.get("hostname", node.hostname)
        node.platform = payload.get("platform", node.platform)
        node.capabilities = [
            NodeCapability.from_dict(c)
            for c in payload.get("capabilities", [])
        ]
        node.last_seen = datetime.now()
        
        # Check if node is paired
        if node.status == NodeStatus.PENDING:
            if self.auto_approve:
                node.status = NodeStatus.PAIRED
                node.paired_at = datetime.now()
                logger.info(f"Auto-approved node {node_id}")
            else:
                # Notify about pending node
                for callback in self._on_node_pending:
                    try:
                        await callback(node)
                    except Exception as e:
                        logger.error(f"Error in on_node_pending callback: {e}")
                
                # Accept connection but note it's pending
                ack = NodeMessage.connect_ack(node_id, paired=False)
                await ws.send_json(ack.to_dict())
                
                logger.info(f"Node {node_id} connected (pending approval)")
                
                # Still track the connection for pending nodes
                conn = NodeConnection(ws, node_id, ip_address)
                self._connections[node_id] = conn
                node.status = NodeStatus.CONNECTED
                self._save_registry()
                return node_id
        
        # Node is paired, accept fully
        node.status = NodeStatus.CONNECTED
        
        # Create connection
        conn = NodeConnection(ws, node_id, ip_address)
        self._connections[node_id] = conn
        
        # Send ACK
        ack = NodeMessage.connect_ack(node_id, paired=True)
        await ws.send_json(ack.to_dict())
        
        # Notify callbacks
        for callback in self._on_node_connected:
            try:
                await callback(node)
            except Exception as e:
                logger.error(f"Error in on_node_connected callback: {e}")
        
        self._save_registry()
        logger.info(f"Node {node_id} connected and paired")
        
        return node_id
    
    async def disconnect_node(self, node_id: str) -> None:
        """Disconnect a node."""
        conn = self._connections.pop(node_id, None)
        if conn:
            conn.close_pending_invokes()
            try:
                if not conn.ws.closed:
                    await conn.ws.close()
            except Exception:
                pass
        
        if node_id in self._nodes:
            node = self._nodes[node_id]
            if node.status == NodeStatus.CONNECTED:
                # Keep paired status if was paired
                if node.paired_at:
                    node.status = NodeStatus.PAIRED
                else:
                    node.status = NodeStatus.DISCONNECTED
            
            node.last_seen = datetime.now()
            
            # Notify callbacks
            for callback in self._on_node_disconnected:
                try:
                    await callback(node)
                except Exception as e:
                    logger.error(f"Error in on_node_disconnected callback: {e}")
            
            self._save_registry()
            logger.info(f"Node {node_id} disconnected")
    
    async def approve_node(self, node_id: str) -> bool:
        """
        Approve a pending node for pairing.
        
        Args:
            node_id: The node ID to approve
        
        Returns:
            True if approved, False if node not found or already paired
        """
        node = self._nodes.get(node_id)
        if not node:
            return False
        
        if node.status not in (NodeStatus.PENDING, NodeStatus.CONNECTED):
            return False
        
        node.status = NodeStatus.PAIRED if node_id not in self._connections else NodeStatus.CONNECTED
        node.paired_at = datetime.now()
        
        # If connected, notify the node
        conn = self._connections.get(node_id)
        if conn:
            ack = NodeMessage.connect_ack(node_id, paired=True)
            try:
                await conn.send(ack)
            except Exception as e:
                logger.warning(f"Failed to notify node of approval: {e}")
        
        self._save_registry()
        logger.info(f"Node {node_id} approved")
        return True
    
    async def reject_node(self, node_id: str, reason: str = "") -> bool:
        """
        Reject a pending node.
        
        Args:
            node_id: The node ID to reject
            reason: Optional reason for rejection
        
        Returns:
            True if rejected, False if node not found
        """
        node = self._nodes.get(node_id)
        if not node:
            return False
        
        # Disconnect if connected
        conn = self._connections.get(node_id)
        if conn:
            reject = NodeMessage.connect_reject(node_id, reason)
            try:
                await conn.send(reject)
            except Exception:
                pass
            await self.disconnect_node(node_id)
        
        # Remove from registry
        del self._nodes[node_id]
        self._save_registry()
        
        logger.info(f"Node {node_id} rejected")
        return True
    
    async def invoke(
        self,
        node_id: str,
        command: str,
        params: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> NodeInvokeResult:
        """
        Invoke a command on a node.
        
        Args:
            node_id: The target node ID
            command: Command name (e.g., "system.run")
            params: Command parameters
            timeout_ms: Timeout in milliseconds
        
        Returns:
            NodeInvokeResult with the command result
        """
        node = self._nodes.get(node_id)
        if not node:
            return NodeInvokeResult(
                invoke_id="",
                success=False,
                error=f"Node {node_id} not found",
                error_code=NodeErrorCode.NODE_UNAVAILABLE,
            )
        
        if not node.paired_at:
            return NodeInvokeResult(
                invoke_id="",
                success=False,
                error=f"Node {node_id} is not paired",
                error_code=NodeErrorCode.NODE_NOT_PAIRED,
            )
        
        conn = self._connections.get(node_id)
        if not conn:
            return NodeInvokeResult(
                invoke_id="",
                success=False,
                error=f"Node {node_id} is not connected",
                error_code=NodeErrorCode.NODE_UNAVAILABLE,
            )
        
        # Check capability
        if not node.has_capability(command):
            return NodeInvokeResult(
                invoke_id="",
                success=False,
                error=f"Node {node_id} does not support {command}",
                error_code=NodeErrorCode.CAPABILITY_NOT_SUPPORTED,
            )
        
        # Create and send invoke
        invoke = NodeInvoke(
            command=command,
            params=params or {},
            timeout_ms=timeout_ms,
        )
        
        return await conn.invoke(invoke)
    
    def get_node(self, node_id: str) -> NodeInfo | None:
        """Get a node by ID."""
        return self._nodes.get(node_id)
    
    def get_node_by_name(self, name: str) -> NodeInfo | None:
        """Get a node by display name."""
        for node in self._nodes.values():
            if node.display_name == name:
                return node
        return None
    
    def list_nodes(
        self,
        status: NodeStatus | None = None,
        connected_only: bool = False,
    ) -> list[NodeInfo]:
        """
        List all nodes.
        
        Args:
            status: Filter by status
            connected_only: Only return connected nodes
        
        Returns:
            List of NodeInfo objects
        """
        nodes = list(self._nodes.values())
        
        if status:
            nodes = [n for n in nodes if n.status == status]
        
        if connected_only:
            nodes = [n for n in nodes if n.id in self._connections]
        
        return nodes
    
    def list_pending(self) -> list[NodeInfo]:
        """List nodes pending approval."""
        return [
            n for n in self._nodes.values()
            if n.status in (NodeStatus.PENDING,) or not n.paired_at
        ]
    
    def is_connected(self, node_id: str) -> bool:
        """Check if a node is currently connected."""
        return node_id in self._connections
    
    def get_default_node(self) -> NodeInfo | None:
        """Get the first connected and paired node."""
        for node_id, conn in self._connections.items():
            node = self._nodes.get(node_id)
            if node and node.paired_at:
                return node
        return None
    
    def on_node_connected(
        self,
        callback: Callable[[NodeInfo], Awaitable[None]],
    ) -> None:
        """Register a callback for when a node connects."""
        self._on_node_connected.append(callback)
    
    def on_node_disconnected(
        self,
        callback: Callable[[NodeInfo], Awaitable[None]],
    ) -> None:
        """Register a callback for when a node disconnects."""
        self._on_node_disconnected.append(callback)
    
    def on_node_pending(
        self,
        callback: Callable[[NodeInfo], Awaitable[None]],
    ) -> None:
        """Register a callback for when a new node is pending approval."""
        self._on_node_pending.append(callback)


# Global instance
_node_manager: NodeManager | None = None


def get_node_manager() -> NodeManager | None:
    """Get the global NodeManager instance."""
    return _node_manager


def set_node_manager(manager: NodeManager) -> None:
    """Set the global NodeManager instance."""
    global _node_manager
    _node_manager = manager
