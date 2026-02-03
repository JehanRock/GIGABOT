"""
Node protocol definitions for GigaBot.

Defines the data structures and message types used for communication
between the gateway and node hosts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class NodeStatus(str, Enum):
    """Status of a node in the system."""
    PENDING = "pending"          # Waiting for pairing approval
    PAIRED = "paired"            # Approved but not connected
    CONNECTED = "connected"      # Actively connected
    DISCONNECTED = "disconnected"  # Was connected, now offline


class NodeMessageType(str, Enum):
    """Types of messages in the node protocol."""
    # Connection lifecycle
    CONNECT = "connect"          # Node → Gateway: Initial connection
    CONNECT_ACK = "connect_ack"  # Gateway → Node: Connection accepted
    CONNECT_REJECT = "connect_reject"  # Gateway → Node: Connection rejected
    DISCONNECT = "disconnect"    # Either direction: Graceful disconnect
    
    # Health
    PING = "ping"                # Either direction
    PONG = "pong"                # Either direction
    
    # Command invocation
    INVOKE = "invoke"            # Gateway → Node: Execute command
    INVOKE_RESULT = "invoke_result"  # Node → Gateway: Command result
    
    # Status
    STATUS = "status"            # Either direction: Status update
    CAPABILITIES = "capabilities"  # Node → Gateway: Advertise capabilities


@dataclass
class NodeCapability:
    """
    A capability that a node can provide.
    
    Capabilities are command namespaces that nodes advertise,
    such as 'system.run', 'system.which', etc.
    """
    name: str                    # e.g., "system.run", "system.which"
    description: str = ""        # Human-readable description
    version: str = "1.0"         # Capability version
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional info
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeCapability":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            metadata=data.get("metadata", {}),
        )


# Standard capabilities
CAPABILITY_SYSTEM_RUN = NodeCapability(
    name="system.run",
    description="Execute shell commands",
)
CAPABILITY_SYSTEM_WHICH = NodeCapability(
    name="system.which",
    description="Check if a command exists",
)
CAPABILITY_SYSTEM_NOTIFY = NodeCapability(
    name="system.notify",
    description="Send system notifications",
)


@dataclass
class NodeInfo:
    """
    Information about a node.
    
    Contains identity, status, capabilities, and connection metadata.
    """
    id: str                      # Unique node identifier
    display_name: str = ""       # Human-readable name
    status: NodeStatus = NodeStatus.PENDING
    capabilities: list[NodeCapability] = field(default_factory=list)
    
    # Connection info
    ip_address: str = ""         # IP address of the node
    hostname: str = ""           # Hostname of the node
    platform: str = ""           # OS platform (linux, darwin, windows)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime | None = None
    paired_at: datetime | None = None
    
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def has_capability(self, name: str) -> bool:
        """Check if node has a specific capability."""
        return any(cap.name == name for cap in self.capabilities)
    
    def get_capability_names(self) -> list[str]:
        """Get list of capability names."""
        return [cap.name for cap in self.capabilities]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "status": self.status.value,
            "capabilities": [cap.to_dict() for cap in self.capabilities],
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "platform": self.platform,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "paired_at": self.paired_at.isoformat() if self.paired_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeInfo":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            display_name=data.get("display_name", ""),
            status=NodeStatus(data.get("status", "pending")),
            capabilities=[
                NodeCapability.from_dict(cap) 
                for cap in data.get("capabilities", [])
            ],
            ip_address=data.get("ip_address", ""),
            hostname=data.get("hostname", ""),
            platform=data.get("platform", ""),
            created_at=datetime.fromisoformat(data["created_at"]) 
                if data.get("created_at") else datetime.now(),
            last_seen=datetime.fromisoformat(data["last_seen"]) 
                if data.get("last_seen") else None,
            paired_at=datetime.fromisoformat(data["paired_at"]) 
                if data.get("paired_at") else None,
            metadata=data.get("metadata", {}),
        )


@dataclass
class NodeInvoke:
    """
    A command invocation request sent to a node.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command: str = ""            # Command name (e.g., "system.run")
    params: dict[str, Any] = field(default_factory=dict)  # Command parameters
    timeout_ms: int = 30000      # Timeout in milliseconds
    idempotency_key: str = ""    # Optional idempotency key
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "command": self.command,
            "params": self.params,
            "timeout_ms": self.timeout_ms,
            "idempotency_key": self.idempotency_key,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeInvoke":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            command=data.get("command", ""),
            params=data.get("params", {}),
            timeout_ms=data.get("timeout_ms", 30000),
            idempotency_key=data.get("idempotency_key", ""),
        )


@dataclass
class NodeInvokeResult:
    """
    Result of a command invocation on a node.
    """
    invoke_id: str               # ID of the original invoke
    success: bool = True
    result: Any = None           # Command result data
    error: str = ""              # Error message if failed
    error_code: str = ""         # Error code (e.g., "PERMISSION_DENIED")
    duration_ms: float = 0.0     # Execution time
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "invoke_id": self.invoke_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "error_code": self.error_code,
            "duration_ms": self.duration_ms,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeInvokeResult":
        """Create from dictionary."""
        return cls(
            invoke_id=data.get("invoke_id", ""),
            success=data.get("success", True),
            result=data.get("result"),
            error=data.get("error", ""),
            error_code=data.get("error_code", ""),
            duration_ms=data.get("duration_ms", 0.0),
        )


@dataclass
class NodeMessage:
    """
    A message in the node protocol.
    
    All communication between gateway and nodes uses this format.
    """
    type: NodeMessageType
    node_id: str = ""            # Node identifier
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "node_id": self.node_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeMessage":
        """Create from dictionary."""
        return cls(
            type=NodeMessageType(data.get("type", "status")),
            node_id=data.get("node_id", ""),
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) 
                if data.get("timestamp") else datetime.now(),
            message_id=data.get("message_id", str(uuid.uuid4())),
        )
    
    @classmethod
    def connect(
        cls,
        node_id: str,
        display_name: str,
        capabilities: list[NodeCapability],
        platform: str = "",
        hostname: str = "",
        token: str = "",
    ) -> "NodeMessage":
        """Create a CONNECT message."""
        return cls(
            type=NodeMessageType.CONNECT,
            node_id=node_id,
            payload={
                "display_name": display_name,
                "capabilities": [cap.to_dict() for cap in capabilities],
                "platform": platform,
                "hostname": hostname,
                "token": token,
            },
        )
    
    @classmethod
    def connect_ack(cls, node_id: str, paired: bool = False) -> "NodeMessage":
        """Create a CONNECT_ACK message."""
        return cls(
            type=NodeMessageType.CONNECT_ACK,
            node_id=node_id,
            payload={"paired": paired},
        )
    
    @classmethod
    def connect_reject(cls, node_id: str, reason: str = "") -> "NodeMessage":
        """Create a CONNECT_REJECT message."""
        return cls(
            type=NodeMessageType.CONNECT_REJECT,
            node_id=node_id,
            payload={"reason": reason},
        )
    
    @classmethod
    def invoke(cls, node_id: str, invoke: NodeInvoke) -> "NodeMessage":
        """Create an INVOKE message."""
        return cls(
            type=NodeMessageType.INVOKE,
            node_id=node_id,
            payload=invoke.to_dict(),
        )
    
    @classmethod
    def invoke_result(cls, node_id: str, result: NodeInvokeResult) -> "NodeMessage":
        """Create an INVOKE_RESULT message."""
        return cls(
            type=NodeMessageType.INVOKE_RESULT,
            node_id=node_id,
            payload=result.to_dict(),
        )
    
    @classmethod
    def ping(cls, node_id: str = "") -> "NodeMessage":
        """Create a PING message."""
        return cls(type=NodeMessageType.PING, node_id=node_id)
    
    @classmethod
    def pong(cls, node_id: str = "") -> "NodeMessage":
        """Create a PONG message."""
        return cls(type=NodeMessageType.PONG, node_id=node_id)


# Error codes
class NodeErrorCode:
    """Standard error codes for node operations."""
    PERMISSION_DENIED = "PERMISSION_DENIED"
    COMMAND_NOT_FOUND = "COMMAND_NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    NODE_UNAVAILABLE = "NODE_UNAVAILABLE"
    NODE_NOT_PAIRED = "NODE_NOT_PAIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    CAPABILITY_NOT_SUPPORTED = "CAPABILITY_NOT_SUPPORTED"
    EXEC_APPROVAL_REQUIRED = "EXEC_APPROVAL_REQUIRED"
    EXEC_DENIED = "EXEC_DENIED"
