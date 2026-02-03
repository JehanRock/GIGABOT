"""
Nodes system for GigaBot.

Enables remote command execution across multiple devices via WebSocket connections.
"""

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
from nanobot.nodes.manager import NodeManager, NodeConnection, get_node_manager, set_node_manager
from nanobot.nodes.router import ExecRouter, ExecHost, ExecResult, get_exec_router, set_exec_router
from nanobot.nodes.approvals import ExecApprovalManager, ApprovalEntry, ApprovalResult
from nanobot.nodes.host import NodeHost, run_node_host

__all__ = [
    # Protocol
    "NodeStatus",
    "NodeCapability",
    "NodeInfo",
    "NodeInvoke",
    "NodeInvokeResult",
    "NodeMessage",
    "NodeMessageType",
    "NodeErrorCode",
    # Manager
    "NodeManager",
    "NodeConnection",
    "get_node_manager",
    "set_node_manager",
    # Router
    "ExecRouter",
    "ExecHost",
    "ExecResult",
    "get_exec_router",
    "set_exec_router",
    # Approvals
    "ExecApprovalManager",
    "ApprovalEntry",
    "ApprovalResult",
    # Host
    "NodeHost",
    "run_node_host",
]
