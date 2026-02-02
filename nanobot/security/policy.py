"""
Tool policy system for GigaBot.

Controls which tools can be used and under what conditions.
Supports:
- Allow/deny lists
- Tool groups
- Elevated mode for dangerous operations
- Human approval workflows
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any
from fnmatch import fnmatch


class PolicyDecision(str, Enum):
    """Result of a policy check."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_ELEVATED = "require_elevated"


@dataclass
class ToolPolicy:
    """
    Tool access policy configuration.
    
    Tools are checked in order:
    1. If in deny list -> DENY
    2. If requires approval and not approved -> REQUIRE_APPROVAL
    3. If in dangerous group and not elevated -> REQUIRE_ELEVATED
    4. If in allow list or allow is ["*"] -> ALLOW
    5. Otherwise -> DENY
    """
    
    # Basic allow/deny
    allow: list[str] = field(default_factory=lambda: ["*"])
    deny: list[str] = field(default_factory=list)
    
    # Tool groups for easier management
    groups: dict[str, list[str]] = field(default_factory=lambda: {
        "filesystem": ["read_file", "write_file", "edit_file", "list_dir"],
        "web": ["web_fetch", "web_search"],
        "shell": ["exec"],
        "dangerous": ["exec", "browser", "gateway", "spawn"],
        "messaging": ["message"],
        "memory": ["memory_store", "memory_search"],
    })
    
    # Tools that require human approval
    require_approval: list[str] = field(default_factory=list)
    
    # Tools that require elevated mode
    require_elevated: list[str] = field(default_factory=lambda: ["gateway"])
    
    # Current elevated state
    elevated: bool = False
    
    # Approved tool calls (by call ID)
    approved_calls: set[str] = field(default_factory=set)
    
    def expand_group(self, name: str) -> list[str]:
        """Expand a group name to its tool list."""
        if name.startswith("@"):
            group_name = name[1:]
            return self.groups.get(group_name, [])
        return [name]
    
    def matches(self, tool_name: str, patterns: list[str]) -> bool:
        """Check if tool name matches any pattern in list."""
        for pattern in patterns:
            # Expand groups
            expanded = self.expand_group(pattern)
            for p in expanded:
                if fnmatch(tool_name, p):
                    return True
        return False


def check_tool_access(
    policy: ToolPolicy,
    tool_name: str,
    call_id: str = "",
    arguments: dict[str, Any] | None = None,
) -> PolicyDecision:
    """
    Check if a tool call is allowed by the policy.
    
    Args:
        policy: The tool policy to check against.
        tool_name: Name of the tool being called.
        call_id: Unique ID of this tool call (for approval tracking).
        arguments: Tool arguments (for advanced policy checks).
    
    Returns:
        PolicyDecision indicating the action to take.
    """
    # 1. Check deny list first
    if policy.matches(tool_name, policy.deny):
        return PolicyDecision.DENY
    
    # 2. Check if requires approval
    if policy.matches(tool_name, policy.require_approval):
        if call_id and call_id in policy.approved_calls:
            pass  # Already approved, continue checking
        else:
            return PolicyDecision.REQUIRE_APPROVAL
    
    # 3. Check if requires elevated mode
    if policy.matches(tool_name, policy.require_elevated):
        if not policy.elevated:
            return PolicyDecision.REQUIRE_ELEVATED
    
    # 4. Check allow list
    if policy.matches(tool_name, policy.allow):
        return PolicyDecision.ALLOW
    
    # 5. Default deny
    return PolicyDecision.DENY


def approve_tool_call(policy: ToolPolicy, call_id: str) -> None:
    """Mark a tool call as approved."""
    policy.approved_calls.add(call_id)


def enter_elevated_mode(policy: ToolPolicy) -> None:
    """Enter elevated mode for dangerous operations."""
    policy.elevated = True


def exit_elevated_mode(policy: ToolPolicy) -> None:
    """Exit elevated mode."""
    policy.elevated = False


# Predefined policy templates
POLICY_PERMISSIVE = ToolPolicy(
    allow=["*"],
    deny=[],
    require_approval=[],
    require_elevated=["gateway"],
)

POLICY_RESTRICTED = ToolPolicy(
    allow=["@filesystem", "@web", "@memory", "message"],
    deny=["@dangerous"],
    require_approval=["write_file", "edit_file"],
    require_elevated=["exec", "gateway"],
)

POLICY_READONLY = ToolPolicy(
    allow=["read_file", "list_dir", "@web", "memory_search"],
    deny=["*"],
    require_approval=[],
    require_elevated=[],
)


def create_policy_from_config(config: dict[str, Any]) -> ToolPolicy:
    """
    Create a ToolPolicy from configuration dict.
    
    Args:
        config: Dictionary with policy settings.
    
    Returns:
        Configured ToolPolicy instance.
    """
    return ToolPolicy(
        allow=config.get("allow", ["*"]),
        deny=config.get("deny", []),
        groups=config.get("groups", ToolPolicy().groups),
        require_approval=config.get("require_approval", []),
        require_elevated=config.get("require_elevated", ["gateway"]),
    )
