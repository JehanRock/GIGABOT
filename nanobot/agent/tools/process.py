"""
Process management tool for GigaBot.

Provides process control for:
- Listing running processes
- Starting/stopping processes
- Background process management
"""

import asyncio
import os
import signal
from typing import Any

from nanobot.agent.tools.base import BaseTool


class ProcessTool(BaseTool):
    """
    Process management tool.
    
    Supports:
    - list: List managed processes
    - start: Start a background process
    - stop: Stop a process by ID
    - status: Get process status
    - signal: Send signal to process
    """
    
    name = "process"
    description = """Manage background processes.
    
Actions:
- list: List all managed processes
- start: Start a background command
- stop: Stop a process by ID
- status: Get status of a process
- signal: Send a signal to a process

Examples:
- List: {"action": "list"}
- Start: {"action": "start", "command": "python script.py", "name": "my-script"}
- Stop: {"action": "stop", "id": "abc123"}
- Status: {"action": "status", "id": "abc123"}
"""
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "start", "stop", "status", "signal"],
                "description": "The process action to perform"
            },
            "command": {
                "type": "string",
                "description": "Command for start action"
            },
            "name": {
                "type": "string",
                "description": "Optional name for the process"
            },
            "id": {
                "type": "string",
                "description": "Process ID for stop/status/signal actions"
            },
            "signal_name": {
                "type": "string",
                "enum": ["SIGTERM", "SIGKILL", "SIGINT", "SIGHUP"],
                "description": "Signal for signal action",
                "default": "SIGTERM"
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for start action"
            }
        },
        "required": ["action"]
    }
    
    def __init__(self, working_dir: str = ""):
        self.working_dir = working_dir
        self._processes: dict[str, dict[str, Any]] = {}
        self._counter = 0
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute process action."""
        action = kwargs.get("action", "")
        
        try:
            if action == "list":
                return self._list_processes()
            
            elif action == "start":
                return await self._start_process(
                    kwargs.get("command", ""),
                    kwargs.get("name", ""),
                    kwargs.get("working_dir", self.working_dir),
                )
            
            elif action == "stop":
                return await self._stop_process(kwargs.get("id", ""))
            
            elif action == "status":
                return self._get_status(kwargs.get("id", ""))
            
            elif action == "signal":
                return await self._send_signal(
                    kwargs.get("id", ""),
                    kwargs.get("signal_name", "SIGTERM"),
                )
            
            else:
                return f"Unknown action: {action}"
                
        except Exception as e:
            return f"Process error: {str(e)}"
    
    def _generate_id(self) -> str:
        """Generate a unique process ID."""
        import hashlib
        import time
        
        self._counter += 1
        data = f"{time.time()}-{self._counter}"
        return hashlib.sha256(data.encode()).hexdigest()[:8]
    
    def _list_processes(self) -> str:
        """List all managed processes."""
        if not self._processes:
            return "No managed processes"
        
        lines = ["Managed Processes:", ""]
        for pid, info in self._processes.items():
            proc: asyncio.subprocess.Process = info["process"]
            status = "running" if proc.returncode is None else f"exited ({proc.returncode})"
            lines.append(f"  [{pid}] {info['name']} - {status}")
            lines.append(f"      Command: {info['command'][:50]}...")
        
        return "\n".join(lines)
    
    async def _start_process(
        self, 
        command: str, 
        name: str = "",
        working_dir: str = "",
    ) -> str:
        """Start a background process."""
        if not command:
            return "Error: Command required for start action"
        
        pid = self._generate_id()
        name = name or f"process-{pid}"
        cwd = working_dir or self.working_dir or None
        
        # Start process
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        
        self._processes[pid] = {
            "process": proc,
            "command": command,
            "name": name,
            "cwd": cwd,
            "pid": proc.pid,
        }
        
        return f"Started process [{pid}] '{name}' (PID: {proc.pid})"
    
    async def _stop_process(self, pid: str) -> str:
        """Stop a process by ID."""
        if not pid:
            return "Error: ID required for stop action"
        
        if pid not in self._processes:
            return f"Error: Process {pid} not found"
        
        info = self._processes[pid]
        proc: asyncio.subprocess.Process = info["process"]
        
        if proc.returncode is not None:
            return f"Process {pid} already exited with code {proc.returncode}"
        
        proc.terminate()
        
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return f"Process {pid} terminated"
        except asyncio.TimeoutError:
            proc.kill()
            return f"Process {pid} killed (did not terminate gracefully)"
    
    def _get_status(self, pid: str) -> str:
        """Get status of a process."""
        if not pid:
            return "Error: ID required for status action"
        
        if pid not in self._processes:
            return f"Error: Process {pid} not found"
        
        info = self._processes[pid]
        proc: asyncio.subprocess.Process = info["process"]
        
        status = "running" if proc.returncode is None else f"exited ({proc.returncode})"
        
        return f"""Process {pid}:
  Name: {info['name']}
  Status: {status}
  System PID: {info['pid']}
  Command: {info['command']}
  Working Dir: {info['cwd'] or '(default)'}"""
    
    async def _send_signal(self, pid: str, signal_name: str) -> str:
        """Send a signal to a process."""
        if not pid:
            return "Error: ID required for signal action"
        
        if pid not in self._processes:
            return f"Error: Process {pid} not found"
        
        info = self._processes[pid]
        proc: asyncio.subprocess.Process = info["process"]
        
        if proc.returncode is not None:
            return f"Process {pid} already exited"
        
        # Map signal name to signal number
        signals = {
            "SIGTERM": signal.SIGTERM,
            "SIGKILL": signal.SIGKILL,
            "SIGINT": signal.SIGINT,
        }
        
        # SIGHUP is not available on Windows
        if hasattr(signal, "SIGHUP"):
            signals["SIGHUP"] = signal.SIGHUP
        
        # Windows compatibility
        if os.name == "nt":
            if signal_name in ("SIGTERM", "SIGINT", "SIGHUP"):
                proc.terminate()
            else:
                proc.kill()
            return f"Sent termination signal to process {pid}"
        
        sig = signals.get(signal_name, signal.SIGTERM)
        proc.send_signal(sig)
        
        return f"Sent {signal_name} to process {pid}"
    
    async def cleanup(self) -> None:
        """Clean up all managed processes."""
        for pid in list(self._processes.keys()):
            try:
                await self._stop_process(pid)
            except Exception:
                pass
        self._processes.clear()
