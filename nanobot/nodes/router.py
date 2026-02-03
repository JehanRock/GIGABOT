"""
Exec Router for GigaBot.

Routes exec commands to either local execution or a connected node.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.nodes.manager import NodeManager


class ExecHost(str, Enum):
    """Where to execute commands."""
    LOCAL = "local"    # Execute on the gateway machine
    NODE = "node"      # Execute on a connected node


@dataclass
class ExecResult:
    """Result of an exec command."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    host: ExecHost = ExecHost.LOCAL
    node_id: str = ""
    error: str = ""
    duration_ms: float = 0.0
    
    def to_output(self) -> str:
        """Convert to tool output string."""
        output_parts = []
        
        if self.stdout:
            output_parts.append(self.stdout)
        
        if self.stderr:
            output_parts.append(f"STDERR: {self.stderr}")
        
        if self.exit_code != 0:
            output_parts.append(f"Exit code: {self.exit_code}")
        
        if self.error:
            output_parts.append(f"Error: {self.error}")
        
        return "\n".join(output_parts) if output_parts else "Command completed successfully"


class ExecRouter:
    """
    Routes exec commands based on configuration.
    
    Supports:
    - Local execution (on gateway machine)
    - Remote execution (via connected nodes)
    - Fallback to local if node unavailable
    """
    
    def __init__(
        self,
        node_manager: "NodeManager | None" = None,
        default_host: ExecHost = ExecHost.LOCAL,
        default_node: str = "",
        fallback_to_local: bool = True,
        local_timeout: int = 60,
    ):
        """
        Initialize the ExecRouter.
        
        Args:
            node_manager: NodeManager for remote execution
            default_host: Default execution host
            default_node: Default node ID or name for remote execution
            fallback_to_local: If True, fallback to local if node unavailable
            local_timeout: Timeout for local execution in seconds
        """
        self._node_manager = node_manager
        self.default_host = default_host
        self.default_node = default_node
        self.fallback_to_local = fallback_to_local
        self.local_timeout = local_timeout
    
    def set_node_manager(self, node_manager: "NodeManager") -> None:
        """Set the node manager."""
        self._node_manager = node_manager
    
    async def execute(
        self,
        command: str,
        host: ExecHost | str | None = None,
        node: str = "",
        cwd: str = "",
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        """
        Execute a command.
        
        Args:
            command: The command to execute
            host: Where to execute (local or node)
            node: Specific node ID or name (if host=node)
            cwd: Working directory
            env: Environment variables
            timeout: Command timeout in seconds
        
        Returns:
            ExecResult with the command output
        """
        # Determine execution host
        if host is None:
            exec_host = self.default_host
        elif isinstance(host, str):
            exec_host = ExecHost(host)
        else:
            exec_host = host
        
        # Route to appropriate executor
        if exec_host == ExecHost.LOCAL:
            return await self._execute_local(command, cwd, env, timeout)
        else:
            return await self._execute_node(command, node, cwd, env, timeout)
    
    async def _execute_local(
        self,
        command: str,
        cwd: str = "",
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        """Execute a command locally."""
        import time
        
        timeout = timeout or self.local_timeout
        start_time = time.time()
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd if cwd else None,
                env=env,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                return ExecResult(
                    success=False,
                    error=f"Command timed out after {timeout}s",
                    host=ExecHost.LOCAL,
                    duration_ms=(time.time() - start_time) * 1000,
                )
            
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            # Truncate if too long
            max_len = 10000
            if len(stdout_str) > max_len:
                stdout_str = stdout_str[:max_len] + f"\n... [truncated, {len(stdout_str)} chars total]"
            if len(stderr_str) > max_len:
                stderr_str = stderr_str[:max_len] + f"\n... [truncated, {len(stderr_str)} chars total]"
            
            return ExecResult(
                success=process.returncode == 0,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode or 0,
                host=ExecHost.LOCAL,
                duration_ms=(time.time() - start_time) * 1000,
            )
            
        except Exception as e:
            return ExecResult(
                success=False,
                error=str(e),
                host=ExecHost.LOCAL,
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    async def _execute_node(
        self,
        command: str,
        node: str = "",
        cwd: str = "",
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        """Execute a command on a remote node."""
        import time
        
        start_time = time.time()
        
        # Check if node manager is available
        if not self._node_manager:
            if self.fallback_to_local:
                logger.debug("No node manager, falling back to local execution")
                return await self._execute_local(command, cwd, env, timeout)
            return ExecResult(
                success=False,
                error="Node manager not configured",
                host=ExecHost.NODE,
            )
        
        # Determine target node
        target_node = node or self.default_node
        
        if target_node:
            # Try by ID first, then by name
            node_info = self._node_manager.get_node(target_node)
            if not node_info:
                node_info = self._node_manager.get_node_by_name(target_node)
        else:
            # Use default connected node
            node_info = self._node_manager.get_default_node()
        
        if not node_info:
            if self.fallback_to_local:
                logger.debug(f"Node '{target_node or 'default'}' not found, falling back to local")
                return await self._execute_local(command, cwd, env, timeout)
            return ExecResult(
                success=False,
                error=f"Node not found: {target_node or 'default'}",
                host=ExecHost.NODE,
            )
        
        # Check if node is connected
        if not self._node_manager.is_connected(node_info.id):
            if self.fallback_to_local:
                logger.debug(f"Node '{node_info.display_name}' not connected, falling back to local")
                return await self._execute_local(command, cwd, env, timeout)
            return ExecResult(
                success=False,
                error=f"Node not connected: {node_info.display_name}",
                host=ExecHost.NODE,
                node_id=node_info.id,
            )
        
        # Build invoke params
        params: dict[str, Any] = {"command": command}
        if cwd:
            params["cwd"] = cwd
        if env:
            params["env"] = env
        if timeout:
            params["timeout"] = timeout
        
        # Invoke on node
        timeout_ms = (timeout or self.local_timeout) * 1000
        result = await self._node_manager.invoke(
            node_id=node_info.id,
            command="system.run",
            params=params,
            timeout_ms=timeout_ms,
        )
        
        # Convert to ExecResult
        if result.success:
            result_data = result.result or {}
            return ExecResult(
                success=result_data.get("exit_code", 0) == 0,
                stdout=result_data.get("stdout", ""),
                stderr=result_data.get("stderr", ""),
                exit_code=result_data.get("exit_code", 0),
                host=ExecHost.NODE,
                node_id=node_info.id,
                duration_ms=result.duration_ms,
            )
        else:
            # Node invocation failed
            if self.fallback_to_local and "not connected" in result.error.lower():
                logger.debug(f"Node execution failed, falling back to local: {result.error}")
                return await self._execute_local(command, cwd, env, timeout)
            
            return ExecResult(
                success=False,
                error=result.error,
                host=ExecHost.NODE,
                node_id=node_info.id,
                duration_ms=result.duration_ms,
            )


# Global instance
_exec_router: ExecRouter | None = None


def get_exec_router() -> ExecRouter:
    """Get the global ExecRouter instance."""
    global _exec_router
    if _exec_router is None:
        _exec_router = ExecRouter()
    return _exec_router


def set_exec_router(router: ExecRouter) -> None:
    """Set the global ExecRouter instance."""
    global _exec_router
    _exec_router = router
