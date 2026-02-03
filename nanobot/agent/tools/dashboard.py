"""
Dashboard Tool for GigaBot Agent.

Allows the agent to modify and deploy its own dashboard UI.
Changes are staged, built, and hot-swapped without service interruption.
"""

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import BaseTool, ToolResult
from nanobot.ui.versions import get_version_manager


class DashboardTool(BaseTool):
    """
    Tool for agent self-modification of the dashboard.
    
    Capabilities:
    - List dashboard files and components
    - Read dashboard source files
    - Update dashboard components
    - Build and deploy changes
    - Rollback to previous versions
    """
    
    name = "dashboard"
    description = """
    Modify the GigaBot dashboard UI. Use this tool to:
    - View current dashboard components and their code
    - Make changes to React components, styles, or configuration
    - Build and deploy UI updates with zero downtime
    - Rollback to previous versions if needed
    
    Changes are staged and built before deployment, ensuring the main
    service continues running during updates.
    """
    
    def __init__(self):
        super().__init__()
        self._version_manager = get_version_manager()
        self._dashboard_dir = Path(__file__).parent.parent.parent / "ui" / "dashboard"
        self._ws_broadcast: callable | None = None
    
    def set_broadcast_handler(self, handler: callable) -> None:
        """Set WebSocket broadcast handler for progress updates."""
        self._ws_broadcast = handler
    
    async def _broadcast_progress(self, event: dict[str, Any]) -> None:
        """Broadcast build progress to connected clients."""
        if self._ws_broadcast:
            await self._ws_broadcast({
                "type": f"dashboard:{event.get('stage', 'progress')}",
                **event,
            })
    
    async def execute(self, action: str, **kwargs) -> ToolResult:
        """
        Execute a dashboard action.
        
        Actions:
        - list_files: List dashboard source files
        - read_file: Read a dashboard file
        - write_file: Update a dashboard file
        - list_versions: List available versions
        - build: Build the dashboard
        - deploy: Deploy staged build
        - rollback: Rollback to a previous version
        - status: Get current dashboard status
        """
        try:
            match action:
                case "list_files":
                    return await self._list_files(**kwargs)
                case "read_file":
                    return await self._read_file(**kwargs)
                case "write_file":
                    return await self._write_file(**kwargs)
                case "list_versions":
                    return await self._list_versions()
                case "build":
                    return await self._build()
                case "deploy":
                    return await self._deploy(**kwargs)
                case "rollback":
                    return await self._rollback(**kwargs)
                case "status":
                    return await self._status()
                case _:
                    return ToolResult(
                        success=False,
                        error=f"Unknown action: {action}. Valid actions: list_files, read_file, write_file, list_versions, build, deploy, rollback, status"
                    )
        except Exception as e:
            logger.error(f"Dashboard tool error: {e}")
            return ToolResult(success=False, error=str(e))
    
    async def _list_files(
        self,
        path: str = "src",
        pattern: str = "**/*.tsx"
    ) -> ToolResult:
        """List dashboard source files."""
        search_path = self._dashboard_dir / path
        
        if not search_path.exists():
            return ToolResult(
                success=False,
                error=f"Path not found: {path}"
            )
        
        files = []
        for file in search_path.glob(pattern):
            rel_path = file.relative_to(self._dashboard_dir)
            files.append({
                "path": str(rel_path),
                "name": file.name,
                "size": file.stat().st_size,
            })
        
        return ToolResult(
            success=True,
            output={
                "files": files,
                "count": len(files),
                "base_path": path,
                "pattern": pattern,
            }
        )
    
    async def _read_file(self, path: str) -> ToolResult:
        """Read a dashboard file."""
        file_path = self._dashboard_dir / path
        
        if not file_path.exists():
            return ToolResult(
                success=False,
                error=f"File not found: {path}"
            )
        
        # Security: ensure path is within dashboard directory
        try:
            file_path.relative_to(self._dashboard_dir)
        except ValueError:
            return ToolResult(
                success=False,
                error="Access denied: path outside dashboard directory"
            )
        
        content = file_path.read_text(encoding="utf-8")
        
        return ToolResult(
            success=True,
            output={
                "path": path,
                "content": content,
                "size": len(content),
                "lines": content.count("\n") + 1,
            }
        )
    
    async def _write_file(self, path: str, content: str) -> ToolResult:
        """Write/update a dashboard file."""
        file_path = self._dashboard_dir / path
        
        # Security: ensure path is within dashboard directory
        try:
            file_path.relative_to(self._dashboard_dir)
        except ValueError:
            return ToolResult(
                success=False,
                error="Access denied: path outside dashboard directory"
            )
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup existing file
        backup_content = None
        if file_path.exists():
            backup_content = file_path.read_text(encoding="utf-8")
        
        try:
            file_path.write_text(content, encoding="utf-8")
            
            return ToolResult(
                success=True,
                output={
                    "path": path,
                    "size": len(content),
                    "lines": content.count("\n") + 1,
                    "is_new": backup_content is None,
                    "message": "File updated. Run 'build' action to compile changes.",
                }
            )
        except Exception as e:
            # Restore backup if write failed
            if backup_content is not None:
                file_path.write_text(backup_content, encoding="utf-8")
            raise
    
    async def _list_versions(self) -> ToolResult:
        """List available dashboard versions."""
        versions = self._version_manager.list_versions()
        current = self._version_manager.get_current_version()
        
        return ToolResult(
            success=True,
            output={
                "current_version": current,
                "versions": versions,
                "count": len(versions),
            }
        )
    
    async def _build(self) -> ToolResult:
        """Build the dashboard."""
        await self._broadcast_progress({"stage": "building", "progress": 0})
        
        # Prepare staging
        prep_result = await self._version_manager.prepare_staging()
        if prep_result.get("status") == "error":
            return ToolResult(
                success=False,
                error=prep_result.get("error", "Failed to prepare staging")
            )
        
        # Build
        build_result = await self._version_manager.build_staging(
            on_progress=lambda p: asyncio.create_task(
                self._broadcast_progress(p)
            )
        )
        
        if build_result.get("status") == "error":
            return ToolResult(
                success=False,
                error=build_result.get("error", "Build failed")
            )
        
        await self._broadcast_progress({"stage": "ready", "progress": 100})
        
        return ToolResult(
            success=True,
            output={
                "message": "Build complete. Run 'deploy' action to go live.",
                "size_bytes": build_result.get("size_bytes"),
                "output_path": build_result.get("output_path"),
            }
        )
    
    async def _deploy(self, version: str | None = None) -> ToolResult:
        """Deploy the staged build."""
        result = await self._version_manager.deploy_staging(version)
        
        if result.get("status") == "error":
            return ToolResult(
                success=False,
                error=result.get("error", "Deployment failed")
            )
        
        # Notify clients to refresh
        await self._broadcast_progress({
            "stage": "refresh",
            "version": result.get("version"),
        })
        
        return ToolResult(
            success=True,
            output={
                "message": f"Deployed version {result.get('version')}",
                "version": result.get("version"),
                "deployed_at": result.get("deployed_at"),
                "size_bytes": result.get("size_bytes"),
            }
        )
    
    async def _rollback(self, version: str) -> ToolResult:
        """Rollback to a previous version."""
        result = await self._version_manager.rollback_to(version)
        
        if result.get("status") == "error":
            return ToolResult(
                success=False,
                error=result.get("error", "Rollback failed")
            )
        
        # Notify clients to refresh
        await self._broadcast_progress({
            "stage": "refresh",
            "version": version,
        })
        
        return ToolResult(
            success=True,
            output={
                "message": f"Rolled back to version {version}",
                "version": version,
                "rolled_back_from": result.get("rolled_back_from"),
            }
        )
    
    async def _status(self) -> ToolResult:
        """Get dashboard status."""
        current = self._version_manager.get_current_version()
        versions = self._version_manager.list_versions()
        
        # Check if source exists
        source_exists = self._dashboard_dir.exists()
        
        # Check if dist exists
        dist_dir = self._version_manager.dist_dir
        dist_exists = dist_dir.exists() and any(dist_dir.iterdir())
        
        return ToolResult(
            success=True,
            output={
                "current_version": current,
                "source_available": source_exists,
                "build_available": dist_exists,
                "version_count": len(versions),
                "dashboard_path": str(self._dashboard_dir),
            }
        )


# Tool schema for registration
DASHBOARD_TOOL_SCHEMA = {
    "name": "dashboard",
    "description": DashboardTool.description,
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list_files",
                    "read_file",
                    "write_file",
                    "list_versions",
                    "build",
                    "deploy",
                    "rollback",
                    "status"
                ],
                "description": "The action to perform"
            },
            "path": {
                "type": "string",
                "description": "File path (for list_files, read_file, write_file)"
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern for list_files (default: **/*.tsx)"
            },
            "content": {
                "type": "string",
                "description": "File content (for write_file)"
            },
            "version": {
                "type": "string",
                "description": "Version string (for deploy, rollback)"
            }
        },
        "required": ["action"]
    }
}
