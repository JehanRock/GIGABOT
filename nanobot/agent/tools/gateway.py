"""
Gateway configuration management tool for GigaBot.

Provides admin-level access to:
- Configuration management
- Channel control
- Provider management
- System status
"""

import json
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import BaseTool


class GatewayTool(BaseTool):
    """
    Gateway admin tool for configuration and system management.
    
    Supports:
    - config: View/update configuration
    - channels: Manage channel settings
    - providers: Manage LLM providers
    - status: Get system status
    - security: View security settings
    
    NOTE: This tool requires elevated permissions.
    """
    
    name = "gateway"
    description = """Admin tool for GigaBot configuration and management.

Actions:
- config_get: Get configuration value
- config_set: Set configuration value
- config_list: List configuration sections
- channels_status: Get channel status
- channels_enable: Enable a channel
- channels_disable: Disable a channel
- providers_list: List configured providers
- providers_test: Test provider connectivity
- status: Get system status
- security_audit: Run security audit

Examples:
- Get config: {"action": "config_get", "path": "agents.defaults.model"}
- Set config: {"action": "config_set", "path": "agents.defaults.model", "value": "gpt-4"}
- Channel status: {"action": "channels_status"}

NOTE: This tool requires elevated mode.
"""
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "config_get", "config_set", "config_list",
                    "channels_status", "channels_enable", "channels_disable",
                    "providers_list", "providers_test",
                    "status", "security_audit"
                ],
                "description": "The gateway action to perform"
            },
            "path": {
                "type": "string",
                "description": "Config path for config actions (e.g., 'agents.defaults.model')"
            },
            "value": {
                "type": "string",
                "description": "Value for config_set action"
            },
            "channel": {
                "type": "string",
                "description": "Channel name for channel actions"
            },
            "provider": {
                "type": "string",
                "description": "Provider name for provider actions"
            }
        },
        "required": ["action"]
    }
    
    def __init__(self, config_path: Path | None = None, config: Any = None):
        self.config_path = config_path
        self.config = config
        self._channel_manager = None  # Set externally if needed
    
    def set_channel_manager(self, manager: Any) -> None:
        """Set the channel manager for channel operations."""
        self._channel_manager = manager
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute gateway action."""
        action = kwargs.get("action", "")
        
        try:
            # Config actions
            if action == "config_get":
                return self._config_get(kwargs.get("path", ""))
            
            elif action == "config_set":
                return self._config_set(kwargs.get("path", ""), kwargs.get("value"))
            
            elif action == "config_list":
                return self._config_list()
            
            # Channel actions
            elif action == "channels_status":
                return self._channels_status()
            
            elif action == "channels_enable":
                return await self._channels_enable(kwargs.get("channel", ""))
            
            elif action == "channels_disable":
                return await self._channels_disable(kwargs.get("channel", ""))
            
            # Provider actions
            elif action == "providers_list":
                return self._providers_list()
            
            elif action == "providers_test":
                return await self._providers_test(kwargs.get("provider", ""))
            
            # System actions
            elif action == "status":
                return self._get_status()
            
            elif action == "security_audit":
                return await self._security_audit()
            
            else:
                return f"Unknown action: {action}"
                
        except Exception as e:
            return f"Gateway error: {str(e)}"
    
    def _config_get(self, path: str) -> str:
        """Get configuration value by path."""
        if not path:
            return "Error: Path required for config_get"
        
        if not self.config:
            return "Error: No configuration loaded"
        
        try:
            value = self._get_nested(self.config, path)
            return f"{path} = {json.dumps(value, indent=2)}"
        except (KeyError, AttributeError):
            return f"Error: Path not found: {path}"
    
    def _config_set(self, path: str, value: Any) -> str:
        """Set configuration value."""
        if not path:
            return "Error: Path required for config_set"
        
        if value is None:
            return "Error: Value required for config_set"
        
        if not self.config:
            return "Error: No configuration loaded"
        
        # Parse value if it's a JSON string
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass  # Keep as string
        
        try:
            self._set_nested(self.config, path, value)
            
            # Save config
            if self.config_path:
                self._save_config()
            
            return f"Set {path} = {value}"
        except (KeyError, AttributeError) as e:
            return f"Error setting config: {str(e)}"
    
    def _config_list(self) -> str:
        """List configuration sections."""
        if not self.config:
            return "Error: No configuration loaded"
        
        sections = []
        for name in dir(self.config):
            if not name.startswith("_") and not callable(getattr(self.config, name)):
                sections.append(name)
        
        return "Configuration sections:\n" + "\n".join(f"  - {s}" for s in sections)
    
    def _get_nested(self, obj: Any, path: str) -> Any:
        """Get nested attribute by dot-separated path."""
        parts = path.split(".")
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                raise KeyError(f"Path component not found: {part}")
        return obj
    
    def _set_nested(self, obj: Any, path: str, value: Any) -> None:
        """Set nested attribute by dot-separated path."""
        parts = path.split(".")
        for part in parts[:-1]:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                raise KeyError(f"Path component not found: {part}")
        
        final_part = parts[-1]
        if hasattr(obj, final_part):
            setattr(obj, final_part, value)
        elif isinstance(obj, dict):
            obj[final_part] = value
        else:
            raise KeyError(f"Cannot set: {final_part}")
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        if not self.config_path or not self.config:
            return
        
        # Convert to dict and save
        config_dict = self.config.model_dump()
        with open(self.config_path, "w") as f:
            json.dump(config_dict, f, indent=2)
    
    def _channels_status(self) -> str:
        """Get status of all channels."""
        if not self._channel_manager:
            # Return config-based status
            if not self.config:
                return "Error: No configuration loaded"
            
            channels = self.config.channels
            lines = ["Channel Status:", ""]
            
            for name in ["telegram", "whatsapp", "discord", "signal", "matrix"]:
                if hasattr(channels, name):
                    ch = getattr(channels, name)
                    enabled = ch.enabled if hasattr(ch, "enabled") else False
                    lines.append(f"  {name}: {'enabled' if enabled else 'disabled'}")
            
            return "\n".join(lines)
        
        status = self._channel_manager.get_status()
        lines = ["Channel Status:", ""]
        
        for name, info in status.items():
            state = "running" if info.get("running") else "stopped"
            lines.append(f"  {name}: {state}")
        
        return "\n".join(lines)
    
    async def _channels_enable(self, channel: str) -> str:
        """Enable a channel."""
        if not channel:
            return "Error: Channel name required"
        
        if not self.config:
            return "Error: No configuration loaded"
        
        channels = self.config.channels
        if not hasattr(channels, channel):
            return f"Error: Unknown channel: {channel}"
        
        ch = getattr(channels, channel)
        ch.enabled = True
        
        if self.config_path:
            self._save_config()
        
        return f"Channel {channel} enabled. Restart required for changes to take effect."
    
    async def _channels_disable(self, channel: str) -> str:
        """Disable a channel."""
        if not channel:
            return "Error: Channel name required"
        
        if not self.config:
            return "Error: No configuration loaded"
        
        channels = self.config.channels
        if not hasattr(channels, channel):
            return f"Error: Unknown channel: {channel}"
        
        ch = getattr(channels, channel)
        ch.enabled = False
        
        if self.config_path:
            self._save_config()
        
        return f"Channel {channel} disabled. Restart required for changes to take effect."
    
    def _providers_list(self) -> str:
        """List configured providers."""
        if not self.config:
            return "Error: No configuration loaded"
        
        providers = self.config.providers
        lines = ["Configured Providers:", ""]
        
        for name in ["anthropic", "openai", "openrouter", "moonshot", "deepseek", "glm", "qwen", "ollama", "vllm"]:
            if hasattr(providers, name):
                p = getattr(providers, name)
                has_key = bool(p.api_key) if hasattr(p, "api_key") else False
                has_base = bool(p.api_base) if hasattr(p, "api_base") else False
                
                status = []
                if has_key:
                    status.append("key configured")
                if has_base:
                    status.append(f"base: {p.api_base}")
                
                lines.append(f"  {name}: {', '.join(status) if status else 'not configured'}")
        
        return "\n".join(lines)
    
    async def _providers_test(self, provider: str) -> str:
        """Test provider connectivity."""
        if not provider:
            return "Error: Provider name required"
        
        # This would need actual provider testing logic
        return f"Provider test for {provider} not implemented yet"
    
    def _get_status(self) -> str:
        """Get system status."""
        import sys
        import platform
        
        lines = [
            "GigaBot Status",
            "=" * 40,
            f"Python: {sys.version.split()[0]}",
            f"Platform: {platform.system()} {platform.release()}",
        ]
        
        if self.config:
            lines.extend([
                f"Default Model: {self.config.agents.defaults.model}",
                f"Workspace: {self.config.agents.defaults.workspace}",
            ])
        
        if self._channel_manager:
            enabled = self._channel_manager.enabled_channels
            lines.append(f"Enabled Channels: {', '.join(enabled) if enabled else 'none'}")
        
        return "\n".join(lines)
    
    async def _security_audit(self) -> str:
        """Run security audit."""
        if not self.config_path:
            return "Error: Config path not set"
        
        try:
            from nanobot.security.audit import run_audit
            from nanobot.utils.helpers import get_workspace_path
            
            workspace = get_workspace_path()
            results, summary, _ = run_audit(self.config_path, workspace, deep=False)
            
            lines = [
                "Security Audit Results",
                "=" * 40,
                f"Score: {summary['score']}%",
                f"Passed: {summary['passed']}/{summary['total_checks']}",
            ]
            
            if summary["critical"] > 0:
                lines.append(f"CRITICAL: {summary['critical']}")
            if summary["errors"] > 0:
                lines.append(f"Errors: {summary['errors']}")
            if summary["warnings"] > 0:
                lines.append(f"Warnings: {summary['warnings']}")
            
            return "\n".join(lines)
            
        except ImportError:
            return "Security audit module not available"
