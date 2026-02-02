"""
Approval system for GigaBot.

Provides human-in-the-loop approval for dangerous operations:
- Pending approval queue
- Approval/denial workflow
- Timeout handling
- Notification callbacks
"""

import asyncio
import time
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class PendingApproval:
    """A pending approval request."""
    id: str
    tool_name: str
    arguments: dict[str, Any]
    requester: str  # session/channel identifier
    reason: str  # Why approval is needed
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision_reason: str = ""
    decided_by: str = ""
    decided_at: float = 0.0
    
    def is_expired(self) -> bool:
        """Check if the approval request has expired."""
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at


class ApprovalManager:
    """
    Manages approval requests for dangerous operations.
    
    Features:
    - Queue pending approvals
    - Notify via callbacks
    - Auto-expire old requests
    - Support for multiple approvers
    """
    
    # Default patterns that require approval
    DANGEROUS_PATTERNS = [
        # File operations
        "rm -rf",
        "rmdir",
        "del /f",
        "format",
        # System operations
        "shutdown",
        "reboot",
        "kill",
        "pkill",
        # Git destructive
        "git push --force",
        "git reset --hard",
        "git clean -fd",
        # Database
        "drop table",
        "drop database",
        "truncate",
        # Network
        "iptables",
        "ufw",
        "firewall",
    ]
    
    def __init__(
        self,
        timeout_seconds: int = 300,
        auto_deny_on_timeout: bool = True,
        dangerous_patterns: list[str] | None = None,
    ):
        """
        Initialize the approval manager.
        
        Args:
            timeout_seconds: Default timeout for approvals.
            auto_deny_on_timeout: Auto-deny when timeout expires.
            dangerous_patterns: Additional patterns requiring approval.
        """
        self.timeout_seconds = timeout_seconds
        self.auto_deny_on_timeout = auto_deny_on_timeout
        
        self.dangerous_patterns = list(self.DANGEROUS_PATTERNS)
        if dangerous_patterns:
            self.dangerous_patterns.extend(dangerous_patterns)
        
        # Pending approvals
        self._pending: dict[str, PendingApproval] = {}
        self._completed: dict[str, PendingApproval] = {}
        
        # Callbacks
        self._on_request: list[Callable[[PendingApproval], Awaitable[None]]] = []
        self._on_decision: list[Callable[[PendingApproval], Awaitable[None]]] = []
        
        # Counter for unique IDs
        self._counter = 0
        
        # Cleanup task
        self._cleanup_task: asyncio.Task | None = None
    
    def needs_approval(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        """
        Check if an operation needs approval.
        
        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.
        
        Returns:
            Tuple of (needs_approval, reason).
        """
        # Check tool name
        if tool_name in ["exec", "shell", "run"]:
            # Check command content
            command = arguments.get("command", "")
            command_lower = command.lower()
            
            for pattern in self.dangerous_patterns:
                if pattern.lower() in command_lower:
                    return True, f"Command contains dangerous pattern: {pattern}"
        
        # Check for file deletion tools
        if tool_name in ["delete", "remove", "rm"]:
            path = arguments.get("path", "")
            if any(p in path for p in ["/", "\\", "*", ".."]):
                return True, f"Deletion of path: {path}"
        
        return False, ""
    
    async def request_approval(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        requester: str,
        reason: str = "",
    ) -> PendingApproval:
        """
        Request approval for an operation.
        
        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.
            requester: Session/channel requesting approval.
            reason: Optional reason for the request.
        
        Returns:
            The pending approval object.
        """
        self._counter += 1
        approval_id = f"approval_{self._counter}_{int(time.time())}"
        
        approval = PendingApproval(
            id=approval_id,
            tool_name=tool_name,
            arguments=arguments,
            requester=requester,
            reason=reason or f"Approval needed for {tool_name}",
            expires_at=time.time() + self.timeout_seconds,
        )
        
        self._pending[approval_id] = approval
        
        logger.info(f"Approval requested: {approval_id} for {tool_name}")
        
        # Notify callbacks
        for callback in self._on_request:
            try:
                await callback(approval)
            except Exception as e:
                logger.error(f"Approval callback error: {e}")
        
        return approval
    
    async def approve(
        self,
        approval_id: str,
        decided_by: str = "user",
        reason: str = "",
    ) -> bool:
        """
        Approve a pending request.
        
        Args:
            approval_id: ID of the approval to grant.
            decided_by: Who approved it.
            reason: Optional reason for approval.
        
        Returns:
            True if approved, False if not found/expired.
        """
        approval = self._pending.get(approval_id)
        
        if not approval:
            logger.warning(f"Approval not found: {approval_id}")
            return False
        
        if approval.is_expired():
            approval.status = ApprovalStatus.EXPIRED
            self._move_to_completed(approval_id)
            return False
        
        approval.status = ApprovalStatus.APPROVED
        approval.decided_by = decided_by
        approval.decision_reason = reason
        approval.decided_at = time.time()
        
        self._move_to_completed(approval_id)
        
        logger.info(f"Approval granted: {approval_id} by {decided_by}")
        
        # Notify callbacks
        for callback in self._on_decision:
            try:
                await callback(approval)
            except Exception as e:
                logger.error(f"Decision callback error: {e}")
        
        return True
    
    async def deny(
        self,
        approval_id: str,
        decided_by: str = "user",
        reason: str = "",
    ) -> bool:
        """
        Deny a pending request.
        
        Args:
            approval_id: ID of the approval to deny.
            decided_by: Who denied it.
            reason: Reason for denial.
        
        Returns:
            True if denied, False if not found.
        """
        approval = self._pending.get(approval_id)
        
        if not approval:
            logger.warning(f"Approval not found: {approval_id}")
            return False
        
        approval.status = ApprovalStatus.DENIED
        approval.decided_by = decided_by
        approval.decision_reason = reason or "Denied by user"
        approval.decided_at = time.time()
        
        self._move_to_completed(approval_id)
        
        logger.info(f"Approval denied: {approval_id} by {decided_by}")
        
        # Notify callbacks
        for callback in self._on_decision:
            try:
                await callback(approval)
            except Exception as e:
                logger.error(f"Decision callback error: {e}")
        
        return True
    
    async def wait_for_decision(
        self,
        approval_id: str,
        timeout: float | None = None,
    ) -> PendingApproval:
        """
        Wait for a decision on an approval.
        
        Args:
            approval_id: ID of the approval to wait for.
            timeout: Optional timeout override.
        
        Returns:
            The approval with its final status.
        
        Raises:
            asyncio.TimeoutError: If timeout expires.
        """
        timeout = timeout or self.timeout_seconds
        start = time.time()
        
        while True:
            # Check if in completed
            if approval_id in self._completed:
                return self._completed[approval_id]
            
            # Check if pending and not expired
            approval = self._pending.get(approval_id)
            if approval:
                if approval.status != ApprovalStatus.PENDING:
                    return approval
                
                if approval.is_expired():
                    if self.auto_deny_on_timeout:
                        await self.deny(approval_id, "system", "Timed out")
                    else:
                        approval.status = ApprovalStatus.EXPIRED
                        self._move_to_completed(approval_id)
                    return approval
            
            # Check overall timeout
            if time.time() - start > timeout:
                raise asyncio.TimeoutError(f"Approval {approval_id} timed out")
            
            await asyncio.sleep(0.5)
    
    def get_pending(self) -> list[PendingApproval]:
        """Get all pending approvals."""
        return list(self._pending.values())
    
    def get_approval(self, approval_id: str) -> PendingApproval | None:
        """Get an approval by ID (pending or completed)."""
        return self._pending.get(approval_id) or self._completed.get(approval_id)
    
    def cancel(self, approval_id: str) -> bool:
        """Cancel a pending approval."""
        approval = self._pending.get(approval_id)
        if not approval:
            return False
        
        approval.status = ApprovalStatus.CANCELLED
        approval.decided_at = time.time()
        self._move_to_completed(approval_id)
        return True
    
    def _move_to_completed(self, approval_id: str) -> None:
        """Move approval from pending to completed."""
        if approval_id in self._pending:
            approval = self._pending.pop(approval_id)
            self._completed[approval_id] = approval
    
    def on_request(self, callback: Callable[[PendingApproval], Awaitable[None]]) -> None:
        """Register a callback for new approval requests."""
        self._on_request.append(callback)
    
    def on_decision(self, callback: Callable[[PendingApproval], Awaitable[None]]) -> None:
        """Register a callback for approval decisions."""
        self._on_decision.append(callback)
    
    async def start_cleanup(self) -> None:
        """Start background task to clean up expired approvals."""
        if self._cleanup_task:
            return
        
        async def cleanup_loop():
            while True:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup(self) -> None:
        """Stop the cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
    
    async def _cleanup_expired(self) -> None:
        """Clean up expired approvals."""
        expired = [
            aid for aid, a in self._pending.items()
            if a.is_expired()
        ]
        
        for approval_id in expired:
            if self.auto_deny_on_timeout:
                await self.deny(approval_id, "system", "Expired")
            else:
                approval = self._pending.get(approval_id)
                if approval:
                    approval.status = ApprovalStatus.EXPIRED
                    self._move_to_completed(approval_id)
        
        # Clean up old completed (keep for 1 hour)
        cutoff = time.time() - 3600
        old = [
            aid for aid, a in self._completed.items()
            if a.decided_at and a.decided_at < cutoff
        ]
        for approval_id in old:
            del self._completed[approval_id]
    
    def get_stats(self) -> dict[str, Any]:
        """Get approval statistics."""
        return {
            "pending_count": len(self._pending),
            "completed_count": len(self._completed),
            "pattern_count": len(self.dangerous_patterns),
            "timeout_seconds": self.timeout_seconds,
        }


# Global instance for convenience
_approval_manager: ApprovalManager | None = None


def get_approval_manager() -> ApprovalManager:
    """Get the global approval manager instance."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager


def set_approval_manager(manager: ApprovalManager) -> None:
    """Set the global approval manager instance."""
    global _approval_manager
    _approval_manager = manager
