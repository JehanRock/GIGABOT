"""Shell execution tool with node routing support."""

import asyncio
import os
from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.nodes.router import ExecRouter


class ExecTool(Tool):
    """
    Tool to execute shell commands.
    
    Supports local execution and remote execution via connected nodes.
    """
    
    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        exec_router: "ExecRouter | None" = None,
        default_host: str = "local",
        default_node: str = "",
    ):
        """
        Initialize the ExecTool.
        
        Args:
            timeout: Default timeout for command execution
            working_dir: Default working directory
            exec_router: ExecRouter for routing to nodes
            default_host: Default execution host ("local" or "node")
            default_node: Default node ID or name for remote execution
        """
        self.timeout = timeout
        self.working_dir = working_dir
        self._exec_router = exec_router
        self.default_host = default_host
        self.default_node = default_node
    
    def set_exec_router(self, router: "ExecRouter") -> None:
        """Set the exec router for node-based execution."""
        self._exec_router = router
    
    @property
    def name(self) -> str:
        return "exec"
    
    @property
    def description(self) -> str:
        return """Execute a shell command and return its output.

Execution can be local (on the gateway machine) or remote (on a connected node).
Use `host="node"` to execute on a remote node, optionally specifying which node.

Examples:
- Local: exec(command="ls -la")
- Remote: exec(command="ls -la", host="node")
- Specific node: exec(command="ls -la", host="node", node="build-server")
"""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command"
                },
                "host": {
                    "type": "string",
                    "enum": ["local", "node"],
                    "description": "Where to execute: 'local' (default) or 'node' (remote node)"
                },
                "node": {
                    "type": "string",
                    "description": "Node ID or name for remote execution (requires host='node')"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Command timeout in seconds"
                }
            },
            "required": ["command"]
        }
    
    async def execute(
        self,
        command: str,
        working_dir: str | None = None,
        host: str | None = None,
        node: str = "",
        timeout: int | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute a shell command.
        
        Args:
            command: The command to execute
            working_dir: Working directory for the command
            host: Where to execute ("local" or "node")
            node: Node ID or name (if host="node")
            timeout: Command timeout in seconds
        
        Returns:
            Command output or error message
        """
        cwd = working_dir or self.working_dir or ""
        exec_timeout = timeout or self.timeout
        exec_host = host or self.default_host
        exec_node = node or self.default_node
        
        # Use exec router if available and host is "node"
        if self._exec_router and exec_host == "node":
            result = await self._exec_router.execute(
                command=command,
                host=exec_host,
                node=exec_node,
                cwd=cwd,
                timeout=exec_timeout,
            )
            return result.to_output()
        
        # Also use router for local execution if available (for consistency)
        if self._exec_router and exec_host == "local":
            result = await self._exec_router.execute(
                command=command,
                host="local",
                cwd=cwd,
                timeout=exec_timeout,
            )
            return result.to_output()
        
        # Fallback to direct local execution
        return await self._execute_local(command, cwd, exec_timeout)
    
    async def _execute_local(
        self,
        command: str,
        cwd: str,
        timeout: int,
    ) -> str:
        """Execute command locally (fallback method)."""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd if cwd else None,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {timeout} seconds"
            
            output_parts = []
            
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")
            
            result = "\n".join(output_parts) if output_parts else "(no output)"
            
            # Truncate very long output
            max_len = 10000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"
            
            return result
            
        except Exception as e:
            return f"Error executing command: {str(e)}"
