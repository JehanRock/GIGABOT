"""
Docker sandbox configuration for GigaBot.

Provides isolated execution environments for tool calls:
- Configurable sandbox modes (off, non-main, all)
- Session or shared scoping
- Workspace access control (none, ro, rw)
- Resource limits (memory, PIDs, network)
"""

import os
import subprocess
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SandboxMode(str, Enum):
    """When to use sandboxing."""
    OFF = "off"          # No sandboxing
    NON_MAIN = "non-main"  # Sandbox subagents only
    ALL = "all"          # Sandbox all tool execution


class SandboxScope(str, Enum):
    """Sandbox instance scope."""
    SHARED = "shared"    # One sandbox for all
    AGENT = "agent"      # One per agent type
    SESSION = "session"  # One per session


class WorkspaceAccess(str, Enum):
    """Workspace mount access level."""
    NONE = "none"        # No workspace access
    READONLY = "ro"      # Read-only access
    READWRITE = "rw"     # Read-write access


@dataclass
class DockerConfig:
    """Docker container configuration."""
    image: str = "debian:bookworm-slim"
    read_only_root: bool = True
    network: str = "none"
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])
    tmpfs: list[str] = field(default_factory=lambda: ["/tmp", "/var/tmp", "/run"])
    pids_limit: int = 100
    memory: str = "512m"
    memory_swap: str = "512m"  # Same as memory = no swap
    cpu_period: int = 100000
    cpu_quota: int = 50000  # 50% of one CPU
    seccomp_profile: str = "default"
    
    # Additional security options
    no_new_privileges: bool = True
    user: str = "nobody"


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    mode: SandboxMode = SandboxMode.OFF
    scope: SandboxScope = SandboxScope.SESSION
    workspace_access: WorkspaceAccess = WorkspaceAccess.READONLY
    docker: DockerConfig = field(default_factory=DockerConfig)
    
    # Allowed paths outside workspace (read-only)
    extra_mounts: list[str] = field(default_factory=list)


def is_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def build_docker_command(
    config: SandboxConfig,
    workspace: Path,
    command: list[str],
    session_id: str = "default",
) -> list[str]:
    """
    Build docker run command with all security options.
    
    Args:
        config: Sandbox configuration.
        workspace: Path to workspace directory.
        command: Command to run inside container.
        session_id: Session identifier for naming.
    
    Returns:
        Complete docker command as list.
    """
    docker = config.docker
    
    cmd = ["docker", "run", "--rm"]
    
    # Container naming
    container_name = f"gigabot-sandbox-{session_id}"
    cmd.extend(["--name", container_name])
    
    # Security: Read-only root filesystem
    if docker.read_only_root:
        cmd.append("--read-only")
    
    # Security: Network isolation
    cmd.extend(["--network", docker.network])
    
    # Security: Drop all capabilities
    for cap in docker.cap_drop:
        cmd.extend(["--cap-drop", cap])
    
    # Security: No new privileges
    if docker.no_new_privileges:
        cmd.append("--security-opt=no-new-privileges")
    
    # Security: Seccomp profile
    if docker.seccomp_profile != "unconfined":
        cmd.append(f"--security-opt=seccomp={docker.seccomp_profile}")
    
    # Security: Run as non-root user
    cmd.extend(["--user", docker.user])
    
    # Resource limits: Memory
    cmd.extend(["--memory", docker.memory])
    cmd.extend(["--memory-swap", docker.memory_swap])
    
    # Resource limits: CPU
    cmd.extend(["--cpu-period", str(docker.cpu_period)])
    cmd.extend(["--cpu-quota", str(docker.cpu_quota)])
    
    # Resource limits: PIDs
    cmd.extend(["--pids-limit", str(docker.pids_limit)])
    
    # Tmpfs mounts for writable directories
    for tmpfs_path in docker.tmpfs:
        cmd.extend(["--tmpfs", f"{tmpfs_path}:rw,noexec,nosuid,size=64m"])
    
    # Workspace mount
    if config.workspace_access != WorkspaceAccess.NONE:
        mount_opts = "ro" if config.workspace_access == WorkspaceAccess.READONLY else "rw"
        cmd.extend(["-v", f"{workspace}:/workspace:{mount_opts}"])
        cmd.extend(["-w", "/workspace"])
    
    # Extra mounts (always read-only)
    for mount_path in config.extra_mounts:
        if os.path.exists(mount_path):
            cmd.extend(["-v", f"{mount_path}:{mount_path}:ro"])
    
    # Image
    cmd.append(docker.image)
    
    # Command
    cmd.extend(command)
    
    return cmd


async def run_in_sandbox(
    config: SandboxConfig,
    workspace: Path,
    command: str,
    session_id: str = "default",
    timeout: float = 30.0,
) -> tuple[int, str, str]:
    """
    Run a command inside a Docker sandbox.
    
    Args:
        config: Sandbox configuration.
        workspace: Path to workspace directory.
        command: Shell command to run.
        session_id: Session identifier.
        timeout: Execution timeout in seconds.
    
    Returns:
        Tuple of (return_code, stdout, stderr).
    """
    import asyncio
    
    if not is_docker_available():
        raise RuntimeError("Docker is not available")
    
    docker_cmd = build_docker_command(
        config,
        workspace,
        ["/bin/sh", "-c", command],
        session_id,
    )
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    except asyncio.TimeoutError:
        # Kill the container
        subprocess.run(
            ["docker", "kill", f"gigabot-sandbox-{session_id}"],
            capture_output=True,
        )
        return -1, "", "Execution timed out"


def should_sandbox(
    config: SandboxConfig,
    is_main_agent: bool = True,
    tool_name: str = "",
) -> bool:
    """
    Determine if a tool call should be sandboxed.
    
    Args:
        config: Sandbox configuration.
        is_main_agent: Whether this is the main agent (vs subagent).
        tool_name: Name of the tool being called.
    
    Returns:
        True if the tool call should run in sandbox.
    """
    if config.mode == SandboxMode.OFF:
        return False
    
    if config.mode == SandboxMode.ALL:
        return True
    
    if config.mode == SandboxMode.NON_MAIN:
        return not is_main_agent
    
    return False


# Predefined sandbox configurations
SANDBOX_DISABLED = SandboxConfig(mode=SandboxMode.OFF)

SANDBOX_STRICT = SandboxConfig(
    mode=SandboxMode.ALL,
    scope=SandboxScope.SESSION,
    workspace_access=WorkspaceAccess.READONLY,
    docker=DockerConfig(
        network="none",
        memory="256m",
        pids_limit=50,
    ),
)

SANDBOX_STANDARD = SandboxConfig(
    mode=SandboxMode.NON_MAIN,
    scope=SandboxScope.SESSION,
    workspace_access=WorkspaceAccess.READWRITE,
    docker=DockerConfig(
        network="none",
        memory="512m",
        pids_limit=100,
    ),
)
