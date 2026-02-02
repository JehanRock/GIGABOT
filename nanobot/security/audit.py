"""
Security audit system for GigaBot.

Performs comprehensive security checks:
- Gateway bind and auth configuration
- Filesystem permissions
- Channel policies
- Tool allowlists
- Elevated access
- Secrets in config
- Plugin trust
"""

import os
import stat
import json
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class AuditSeverity(str, Enum):
    """Severity level of audit findings."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditResult:
    """Result of a single audit check."""
    check_name: str
    passed: bool
    severity: AuditSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    fix_suggestion: str = ""
    auto_fixable: bool = False


@dataclass
class SecurityAudit:
    """Security audit runner."""
    config_path: Path
    workspace_path: Path
    results: list[AuditResult] = field(default_factory=list)
    
    def run_all(self, deep: bool = False) -> list[AuditResult]:
        """
        Run all security checks.
        
        Args:
            deep: If True, run additional deep checks.
        
        Returns:
            List of audit results.
        """
        self.results = []
        
        # Basic checks
        self._check_config_exists()
        self._check_config_permissions()
        self._check_gateway_auth()
        self._check_api_keys()
        self._check_workspace_permissions()
        self._check_channel_allowlists()
        self._check_tool_policies()
        
        # Deep checks (may involve network)
        if deep:
            self._check_gateway_bind()
            self._check_exposed_ports()
        
        return self.results
    
    def _add_result(self, result: AuditResult) -> None:
        """Add a result to the audit."""
        self.results.append(result)
    
    def _load_config(self) -> dict[str, Any] | None:
        """Load configuration file."""
        if not self.config_path.exists():
            return None
        try:
            with open(self.config_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _check_config_exists(self) -> None:
        """Check that config file exists."""
        exists = self.config_path.exists()
        self._add_result(AuditResult(
            check_name="config_exists",
            passed=exists,
            severity=AuditSeverity.ERROR if not exists else AuditSeverity.INFO,
            message="Configuration file exists" if exists else "Configuration file not found",
            details={"path": str(self.config_path)},
            fix_suggestion="Run 'gigabot onboard' to create default configuration",
            auto_fixable=True,
        ))
    
    def _check_config_permissions(self) -> None:
        """Check config file has secure permissions."""
        if not self.config_path.exists():
            return
        
        # On Windows, permission checks are different
        if os.name == "nt":
            # Skip detailed permission check on Windows
            self._add_result(AuditResult(
                check_name="config_permissions",
                passed=True,
                severity=AuditSeverity.INFO,
                message="Permission check skipped on Windows",
                details={"platform": "windows"},
            ))
            return
        
        # Unix permission check
        mode = os.stat(self.config_path).st_mode
        world_readable = mode & stat.S_IROTH
        world_writable = mode & stat.S_IWOTH
        
        secure = not (world_readable or world_writable)
        
        self._add_result(AuditResult(
            check_name="config_permissions",
            passed=secure,
            severity=AuditSeverity.WARNING if not secure else AuditSeverity.INFO,
            message="Config file has secure permissions" if secure else "Config file is world-readable/writable",
            details={"mode": oct(mode)},
            fix_suggestion="Run 'chmod 600 ~/.nanobot/config.json'",
            auto_fixable=True,
        ))
    
    def _check_gateway_auth(self) -> None:
        """Check gateway authentication is properly configured."""
        config = self._load_config()
        if not config:
            return
        
        gateway = config.get("gateway", {})
        security = config.get("security", {})
        auth = security.get("auth", {})
        
        auth_mode = auth.get("mode", "none")
        has_token = bool(auth.get("token"))
        has_password = bool(auth.get("passwordHash"))
        
        if auth_mode == "none":
            self._add_result(AuditResult(
                check_name="gateway_auth",
                passed=False,
                severity=AuditSeverity.CRITICAL,
                message="Gateway authentication is disabled",
                details={"mode": auth_mode},
                fix_suggestion="Set security.auth.mode to 'token' and generate a secure token",
                auto_fixable=True,
            ))
        elif auth_mode == "token" and not has_token:
            self._add_result(AuditResult(
                check_name="gateway_auth",
                passed=False,
                severity=AuditSeverity.CRITICAL,
                message="Token auth enabled but no token configured",
                details={"mode": auth_mode},
                fix_suggestion="Generate a token with 'gigabot security generate-token'",
                auto_fixable=True,
            ))
        elif auth_mode == "token" and has_token and len(auth.get("token", "")) < 24:
            self._add_result(AuditResult(
                check_name="gateway_auth",
                passed=False,
                severity=AuditSeverity.WARNING,
                message="Token is too short (< 24 characters)",
                details={"token_length": len(auth.get("token", ""))},
                fix_suggestion="Use a longer token (24+ characters recommended)",
                auto_fixable=True,
            ))
        else:
            self._add_result(AuditResult(
                check_name="gateway_auth",
                passed=True,
                severity=AuditSeverity.INFO,
                message=f"Gateway authentication configured ({auth_mode})",
                details={"mode": auth_mode},
            ))
    
    def _check_api_keys(self) -> None:
        """Check for exposed API keys in config."""
        config = self._load_config()
        if not config:
            return
        
        providers = config.get("providers", {})
        exposed_keys = []
        
        for provider, settings in providers.items():
            if isinstance(settings, dict):
                api_key = settings.get("apiKey", "")
                if api_key and not api_key.startswith("$"):
                    # Key is hardcoded, not an env var reference
                    exposed_keys.append(provider)
        
        if exposed_keys:
            self._add_result(AuditResult(
                check_name="api_keys_exposure",
                passed=False,
                severity=AuditSeverity.WARNING,
                message=f"API keys are hardcoded for: {', '.join(exposed_keys)}",
                details={"providers": exposed_keys},
                fix_suggestion="Use environment variables (e.g., $ANTHROPIC_API_KEY) instead of hardcoded keys",
                auto_fixable=False,
            ))
        else:
            self._add_result(AuditResult(
                check_name="api_keys_exposure",
                passed=True,
                severity=AuditSeverity.INFO,
                message="No hardcoded API keys found",
            ))
    
    def _check_workspace_permissions(self) -> None:
        """Check workspace directory permissions."""
        if not self.workspace_path.exists():
            self._add_result(AuditResult(
                check_name="workspace_exists",
                passed=False,
                severity=AuditSeverity.ERROR,
                message="Workspace directory does not exist",
                details={"path": str(self.workspace_path)},
                fix_suggestion="Run 'gigabot onboard' to create workspace",
                auto_fixable=True,
            ))
            return
        
        # Check for sensitive files in workspace
        sensitive_patterns = [".env", "credentials", "secret", "password", "token", ".pem", ".key"]
        sensitive_files = []
        
        for pattern in sensitive_patterns:
            for path in self.workspace_path.rglob(f"*{pattern}*"):
                if path.is_file():
                    sensitive_files.append(str(path.relative_to(self.workspace_path)))
        
        if sensitive_files:
            self._add_result(AuditResult(
                check_name="workspace_sensitive_files",
                passed=False,
                severity=AuditSeverity.WARNING,
                message=f"Potentially sensitive files in workspace: {len(sensitive_files)} found",
                details={"files": sensitive_files[:10]},  # Show first 10
                fix_suggestion="Review and remove sensitive files from workspace",
                auto_fixable=False,
            ))
        else:
            self._add_result(AuditResult(
                check_name="workspace_sensitive_files",
                passed=True,
                severity=AuditSeverity.INFO,
                message="No obviously sensitive files in workspace",
            ))
    
    def _check_channel_allowlists(self) -> None:
        """Check channel allowlists are configured."""
        config = self._load_config()
        if not config:
            return
        
        channels = config.get("channels", {})
        open_channels = []
        
        for channel, settings in channels.items():
            if isinstance(settings, dict):
                enabled = settings.get("enabled", False)
                allow_from = settings.get("allowFrom", [])
                
                if enabled and not allow_from:
                    open_channels.append(channel)
        
        if open_channels:
            self._add_result(AuditResult(
                check_name="channel_allowlists",
                passed=False,
                severity=AuditSeverity.WARNING,
                message=f"Channels without allowlists: {', '.join(open_channels)}",
                details={"channels": open_channels},
                fix_suggestion="Add allowFrom lists to restrict who can interact with the bot",
                auto_fixable=False,
            ))
        else:
            enabled_channels = [c for c, s in channels.items() if isinstance(s, dict) and s.get("enabled")]
            if enabled_channels:
                self._add_result(AuditResult(
                    check_name="channel_allowlists",
                    passed=True,
                    severity=AuditSeverity.INFO,
                    message=f"All enabled channels have allowlists configured",
                    details={"channels": enabled_channels},
                ))
    
    def _check_tool_policies(self) -> None:
        """Check tool policy configuration."""
        config = self._load_config()
        if not config:
            return
        
        security = config.get("security", {})
        policy = security.get("toolPolicy", {})
        
        allow = policy.get("allow", ["*"])
        deny = policy.get("deny", [])
        
        if allow == ["*"] and not deny:
            self._add_result(AuditResult(
                check_name="tool_policies",
                passed=False,
                severity=AuditSeverity.WARNING,
                message="All tools are allowed with no restrictions",
                details={"allow": allow, "deny": deny},
                fix_suggestion="Consider restricting dangerous tools like 'exec' and 'gateway'",
                auto_fixable=False,
            ))
        else:
            self._add_result(AuditResult(
                check_name="tool_policies",
                passed=True,
                severity=AuditSeverity.INFO,
                message="Tool policies are configured",
                details={"allow": allow, "deny": deny},
            ))
    
    def _check_gateway_bind(self) -> None:
        """Check gateway bind address (deep check)."""
        config = self._load_config()
        if not config:
            return
        
        gateway = config.get("gateway", {})
        host = gateway.get("host", "0.0.0.0")
        
        if host == "0.0.0.0":
            self._add_result(AuditResult(
                check_name="gateway_bind",
                passed=False,
                severity=AuditSeverity.WARNING,
                message="Gateway binds to all interfaces (0.0.0.0)",
                details={"host": host},
                fix_suggestion="Consider binding to 127.0.0.1 for local-only access",
                auto_fixable=False,
            ))
        else:
            self._add_result(AuditResult(
                check_name="gateway_bind",
                passed=True,
                severity=AuditSeverity.INFO,
                message=f"Gateway binds to {host}",
                details={"host": host},
            ))
    
    def _check_exposed_ports(self) -> None:
        """Check for exposed ports (deep check)."""
        # This is a placeholder for actual network scanning
        # In production, this would check if the gateway port is exposed
        self._add_result(AuditResult(
            check_name="exposed_ports",
            passed=True,
            severity=AuditSeverity.INFO,
            message="Port exposure check not implemented",
            details={"note": "Manual verification recommended"},
        ))
    
    def get_summary(self) -> dict[str, Any]:
        """Get audit summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        by_severity = {
            AuditSeverity.CRITICAL: 0,
            AuditSeverity.ERROR: 0,
            AuditSeverity.WARNING: 0,
            AuditSeverity.INFO: 0,
        }
        
        for result in self.results:
            if not result.passed:
                by_severity[result.severity] += 1
        
        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "critical": by_severity[AuditSeverity.CRITICAL],
            "errors": by_severity[AuditSeverity.ERROR],
            "warnings": by_severity[AuditSeverity.WARNING],
            "score": round(passed / total * 100) if total > 0 else 0,
        }
    
    def fix_auto_fixable(self) -> list[str]:
        """
        Attempt to auto-fix issues that are marked as auto-fixable.
        
        Returns:
            List of fixes applied.
        """
        fixes_applied = []
        
        for result in self.results:
            if not result.passed and result.auto_fixable:
                if result.check_name == "config_permissions" and os.name != "nt":
                    try:
                        os.chmod(self.config_path, 0o600)
                        fixes_applied.append(f"Fixed permissions on {self.config_path}")
                    except OSError:
                        pass
                
                # Add more auto-fixes as needed
        
        return fixes_applied


def run_audit(
    config_path: Path,
    workspace_path: Path,
    deep: bool = False,
    auto_fix: bool = False,
) -> tuple[list[AuditResult], dict[str, Any], list[str]]:
    """
    Run security audit.
    
    Args:
        config_path: Path to config file.
        workspace_path: Path to workspace directory.
        deep: Run deep checks.
        auto_fix: Attempt to fix issues.
    
    Returns:
        Tuple of (results, summary, fixes_applied).
    """
    audit = SecurityAudit(config_path, workspace_path)
    results = audit.run_all(deep=deep)
    summary = audit.get_summary()
    
    fixes = []
    if auto_fix:
        fixes = audit.fix_auto_fixable()
    
    return results, summary, fixes
