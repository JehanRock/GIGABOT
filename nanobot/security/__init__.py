"""
Security module for GigaBot.

Provides multi-layer security:
- Layer 1: Network (bind mode, token/password auth, Tailscale identity)
- Layer 2: Channel (DM pairing, allowlists, group policies)
- Layer 3: Tool (allow/deny lists, elevated mode, human approval)
- Layer 4: Runtime (Docker sandbox, read-only root, network isolation)
"""

from nanobot.security.auth import (
    AuthConfig,
    AuthMode,
    DeviceAuth,
    authenticate_request,
    generate_token,
    verify_token,
    hash_password,
    verify_password,
    verify_device_auth,
    create_device_auth,
)
from nanobot.security.policy import (
    ToolPolicy,
    PolicyDecision,
    check_tool_access,
    approve_tool_call,
    enter_elevated_mode,
    exit_elevated_mode,
    POLICY_PERMISSIVE,
    POLICY_RESTRICTED,
    POLICY_READONLY,
    create_policy_from_config,
)
from nanobot.security.sandbox import (
    SandboxConfig,
    SandboxMode,
    SandboxScope,
    WorkspaceAccess,
    DockerConfig,
    is_docker_available,
    build_docker_command,
    should_sandbox,
    SANDBOX_DISABLED,
    SANDBOX_STRICT,
    SANDBOX_STANDARD,
)
from nanobot.security.audit import (
    SecurityAudit,
    AuditResult,
    AuditSeverity,
    run_audit,
)
from nanobot.security.approval import (
    ApprovalManager,
    ApprovalStatus,
    PendingApproval,
    get_approval_manager,
    set_approval_manager,
)

__all__ = [
    # Auth
    "AuthConfig",
    "AuthMode",
    "DeviceAuth",
    "authenticate_request",
    "generate_token",
    "verify_token",
    "hash_password",
    "verify_password",
    "verify_device_auth",
    "create_device_auth",
    # Policy
    "ToolPolicy",
    "PolicyDecision",
    "check_tool_access",
    "approve_tool_call",
    "enter_elevated_mode",
    "exit_elevated_mode",
    "POLICY_PERMISSIVE",
    "POLICY_RESTRICTED",
    "POLICY_READONLY",
    "create_policy_from_config",
    # Sandbox
    "SandboxConfig",
    "SandboxMode",
    "SandboxScope",
    "WorkspaceAccess",
    "DockerConfig",
    "is_docker_available",
    "build_docker_command",
    "should_sandbox",
    "SANDBOX_DISABLED",
    "SANDBOX_STRICT",
    "SANDBOX_STANDARD",
    # Audit
    "SecurityAudit",
    "AuditResult",
    "AuditSeverity",
    "run_audit",
    # Approval
    "ApprovalManager",
    "ApprovalStatus",
    "PendingApproval",
    "get_approval_manager",
    "set_approval_manager",
]
