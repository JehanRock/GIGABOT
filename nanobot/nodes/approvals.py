"""
Node-local exec approvals for GigaBot.

Manages allowlists for commands that can be executed on this node.
"""

import fnmatch
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class ApprovalResult:
    """Result of an approval check."""
    allowed: bool
    reason: str = ""
    matched_pattern: str = ""


@dataclass
class ApprovalEntry:
    """An entry in the approval list."""
    pattern: str           # Command pattern (glob or regex)
    is_regex: bool = False  # If True, pattern is a regex
    allow: bool = True      # True for allow, False for deny
    added_at: datetime = field(default_factory=datetime.now)
    added_by: str = ""      # Who added this entry
    note: str = ""          # Optional note
    
    def matches(self, command: str) -> bool:
        """Check if this entry matches a command."""
        if self.is_regex:
            try:
                return bool(re.match(self.pattern, command))
            except re.error:
                return False
        else:
            # Glob pattern matching
            return fnmatch.fnmatch(command, self.pattern)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern": self.pattern,
            "is_regex": self.is_regex,
            "allow": self.allow,
            "added_at": self.added_at.isoformat(),
            "added_by": self.added_by,
            "note": self.note,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalEntry":
        """Create from dictionary."""
        return cls(
            pattern=data.get("pattern", ""),
            is_regex=data.get("is_regex", False),
            allow=data.get("allow", True),
            added_at=datetime.fromisoformat(data["added_at"]) 
                if data.get("added_at") else datetime.now(),
            added_by=data.get("added_by", ""),
            note=data.get("note", ""),
        )


class ExecApprovalManager:
    """
    Manages exec command approvals for a node.
    
    Features:
    - Allowlist and denylist patterns
    - Glob and regex pattern matching
    - Persistence to file
    - Default safe commands
    """
    
    # Default safe commands that are always allowed
    DEFAULT_SAFE_PATTERNS = [
        # Read-only commands
        "ls *",
        "dir *",
        "pwd",
        "whoami",
        "hostname",
        "uname *",
        "cat *",
        "head *",
        "tail *",
        "grep *",
        "find *",
        "which *",
        "echo *",
        "date",
        "uptime",
        "df *",
        "du *",
        "free *",
        "ps *",
        "top -b -n 1*",
        "env",
        "printenv*",
        # Git read-only
        "git status*",
        "git log*",
        "git diff*",
        "git show*",
        "git branch*",
        "git remote*",
        # Development tools
        "python --version*",
        "python3 --version*",
        "node --version*",
        "npm --version*",
        "pip --version*",
        "cargo --version*",
        "rustc --version*",
        "go version*",
    ]
    
    # Dangerous patterns that should always be denied
    DEFAULT_DENY_PATTERNS = [
        # Destructive file operations
        "rm -rf /*",
        "rm -rf /",
        "rmdir /*",
        "del /s /q *",
        "format *",
        # System operations
        "shutdown*",
        "reboot*",
        "poweroff*",
        "halt*",
        "init *",
        "systemctl *stop*",
        "systemctl *disable*",
        # Network/firewall
        "iptables -F*",
        "iptables -X*",
        "ufw disable*",
        # Privilege escalation
        "chmod 777 /*",
        "chown -R * /*",
        # Crypto/ransomware patterns
        "*encrypt*all*",
        "*ransom*",
    ]
    
    def __init__(
        self,
        storage_path: Path | None = None,
        allow_by_default: bool = False,
        use_default_safe: bool = True,
        use_default_deny: bool = True,
    ):
        """
        Initialize the ExecApprovalManager.
        
        Args:
            storage_path: Path to store approvals (default: ~/.gigabot/exec-approvals.json)
            allow_by_default: If True, allow commands not in any list
            use_default_safe: If True, include default safe patterns
            use_default_deny: If True, include default deny patterns
        """
        self.storage_path = storage_path or Path.home() / ".gigabot" / "exec-approvals.json"
        self.allow_by_default = allow_by_default
        self.use_default_safe = use_default_safe
        self.use_default_deny = use_default_deny
        
        # User-defined entries
        self._entries: list[ApprovalEntry] = []
        
        # Load existing entries
        self._load()
    
    def _load(self) -> None:
        """Load approvals from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self._entries = [
                    ApprovalEntry.from_dict(e) 
                    for e in data.get("entries", [])
                ]
                self.allow_by_default = data.get("allow_by_default", self.allow_by_default)
                self.use_default_safe = data.get("use_default_safe", self.use_default_safe)
                self.use_default_deny = data.get("use_default_deny", self.use_default_deny)
                logger.debug(f"Loaded {len(self._entries)} exec approval entries")
            except Exception as e:
                logger.warning(f"Failed to load exec approvals: {e}")
    
    def _save(self) -> None:
        """Save approvals to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "entries": [e.to_dict() for e in self._entries],
                "allow_by_default": self.allow_by_default,
                "use_default_safe": self.use_default_safe,
                "use_default_deny": self.use_default_deny,
                "updated_at": datetime.now().isoformat(),
            }
            self.storage_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save exec approvals: {e}")
    
    def check_approval(self, command: str) -> ApprovalResult:
        """
        Check if a command is approved for execution.
        
        The check order is:
        1. User deny entries (explicit deny)
        2. Default deny patterns
        3. User allow entries (explicit allow)
        4. Default safe patterns
        5. Default behavior (allow_by_default)
        
        Args:
            command: The command to check
        
        Returns:
            ApprovalResult with the decision
        """
        command = command.strip()
        
        # 1. Check user deny entries first
        for entry in self._entries:
            if not entry.allow and entry.matches(command):
                return ApprovalResult(
                    allowed=False,
                    reason="Matched user deny pattern",
                    matched_pattern=entry.pattern,
                )
        
        # 2. Check default deny patterns
        if self.use_default_deny:
            for pattern in self.DEFAULT_DENY_PATTERNS:
                if fnmatch.fnmatch(command, pattern):
                    return ApprovalResult(
                        allowed=False,
                        reason="Matched dangerous pattern",
                        matched_pattern=pattern,
                    )
        
        # 3. Check user allow entries
        for entry in self._entries:
            if entry.allow and entry.matches(command):
                return ApprovalResult(
                    allowed=True,
                    reason="Matched user allow pattern",
                    matched_pattern=entry.pattern,
                )
        
        # 4. Check default safe patterns
        if self.use_default_safe:
            for pattern in self.DEFAULT_SAFE_PATTERNS:
                if fnmatch.fnmatch(command, pattern):
                    return ApprovalResult(
                        allowed=True,
                        reason="Matched safe pattern",
                        matched_pattern=pattern,
                    )
        
        # 5. Default behavior
        if self.allow_by_default:
            return ApprovalResult(
                allowed=True,
                reason="Default allow",
            )
        else:
            return ApprovalResult(
                allowed=False,
                reason="Not in allowlist",
            )
    
    def add_allow(
        self,
        pattern: str,
        is_regex: bool = False,
        added_by: str = "",
        note: str = "",
    ) -> None:
        """Add an allow pattern."""
        entry = ApprovalEntry(
            pattern=pattern,
            is_regex=is_regex,
            allow=True,
            added_by=added_by,
            note=note,
        )
        self._entries.append(entry)
        self._save()
        logger.info(f"Added allow pattern: {pattern}")
    
    def add_deny(
        self,
        pattern: str,
        is_regex: bool = False,
        added_by: str = "",
        note: str = "",
    ) -> None:
        """Add a deny pattern."""
        entry = ApprovalEntry(
            pattern=pattern,
            is_regex=is_regex,
            allow=False,
            added_by=added_by,
            note=note,
        )
        self._entries.append(entry)
        self._save()
        logger.info(f"Added deny pattern: {pattern}")
    
    def remove(self, pattern: str) -> bool:
        """Remove a pattern from the list."""
        original_count = len(self._entries)
        self._entries = [e for e in self._entries if e.pattern != pattern]
        
        if len(self._entries) < original_count:
            self._save()
            logger.info(f"Removed pattern: {pattern}")
            return True
        return False
    
    def list_entries(self) -> list[ApprovalEntry]:
        """List all user-defined entries."""
        return self._entries.copy()
    
    def set_default_mode(self, allow_by_default: bool) -> None:
        """Set the default mode for unmatched commands."""
        self.allow_by_default = allow_by_default
        self._save()
    
    def clear(self) -> None:
        """Clear all user-defined entries."""
        self._entries = []
        self._save()
        logger.info("Cleared all exec approval entries")


# Global instance
_exec_approval_manager: ExecApprovalManager | None = None


def get_exec_approval_manager() -> ExecApprovalManager:
    """Get the global ExecApprovalManager instance."""
    global _exec_approval_manager
    if _exec_approval_manager is None:
        _exec_approval_manager = ExecApprovalManager()
    return _exec_approval_manager


def set_exec_approval_manager(manager: ExecApprovalManager) -> None:
    """Set the global ExecApprovalManager instance."""
    global _exec_approval_manager
    _exec_approval_manager = manager
