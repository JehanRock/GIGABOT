"""
Dashboard Version Manager for GigaBot.

Provides hot-swap deployment capabilities:
- Prepare staging builds
- Atomic version swapping
- Version history and rollback
"""

import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from loguru import logger


class DashboardVersionManager:
    """
    Manages dashboard versions for hot-swap deployment.
    
    Directory Structure:
    - ui/dist/           -> Active build (or symlink to current version)
    - ui/staging/        -> Build being prepared
    - ui/versions/       -> Historical versions (v1.0.0/, v1.0.1/, etc.)
    """
    
    def __init__(self, ui_dir: Path | None = None):
        self.ui_dir = ui_dir or Path(__file__).parent
        self.dashboard_dir = self.ui_dir / "dashboard"
        self.dist_dir = self.ui_dir / "dist"
        self.staging_dir = self.ui_dir / "staging"
        self.versions_dir = self.ui_dir / "versions"
        
        # Manifest file tracks version metadata
        self.manifest_file = self.ui_dir / "versions.json"
        
        # Build process
        self._build_process: subprocess.Popen | None = None
        self._build_lock = asyncio.Lock()
    
    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_manifest(self) -> dict[str, Any]:
        """Load version manifest."""
        if self.manifest_file.exists():
            try:
                return json.loads(self.manifest_file.read_text())
            except json.JSONDecodeError:
                logger.warning("Invalid manifest file, creating new one")
        
        return {
            "current_version": None,
            "versions": [],
            "last_updated": None,
        }
    
    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        """Save version manifest."""
        manifest["last_updated"] = datetime.utcnow().isoformat()
        self.manifest_file.write_text(json.dumps(manifest, indent=2))
    
    def get_current_version(self) -> str | None:
        """Get the currently deployed version."""
        manifest = self._load_manifest()
        return manifest.get("current_version")
    
    def list_versions(self) -> list[dict[str, Any]]:
        """List all available versions."""
        manifest = self._load_manifest()
        versions = manifest.get("versions", [])
        
        # Mark current version
        current = manifest.get("current_version")
        for v in versions:
            v["is_current"] = v.get("version") == current
        
        return sorted(versions, key=lambda x: x.get("created_at", ""), reverse=True)
    
    async def prepare_staging(self) -> dict[str, Any]:
        """
        Prepare staging directory for a new build.
        
        Returns:
            Status dict with staging info.
        """
        self._ensure_dirs()
        
        # Clear staging directory
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True)
        
        logger.info("Staging directory prepared")
        
        return {
            "status": "ready",
            "staging_path": str(self.staging_dir),
        }
    
    async def build_staging(
        self,
        on_progress: Callable | None = None
    ) -> dict[str, Any]:
        """
        Build the dashboard in staging directory.
        
        Args:
            on_progress: Optional callback for build progress.
        
        Returns:
            Build status dict.
        """
        async with self._build_lock:
            if not self.dashboard_dir.exists():
                return {
                    "status": "error",
                    "error": "Dashboard source directory not found",
                }
            
            # Check if node_modules exists
            node_modules = self.dashboard_dir / "node_modules"
            
            try:
                # Install dependencies if needed
                if not node_modules.exists():
                    logger.info("Installing dashboard dependencies...")
                    if on_progress:
                        on_progress({"stage": "install", "progress": 10})
                    
                    install_proc = await asyncio.create_subprocess_exec(
                        "npm", "install",
                        cwd=str(self.dashboard_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await install_proc.wait()
                    
                    if install_proc.returncode != 0:
                        stderr = await install_proc.stderr.read()
                        return {
                            "status": "error",
                            "error": f"npm install failed: {stderr.decode()}",
                        }
                
                # Run build
                logger.info("Building dashboard...")
                if on_progress:
                    on_progress({"stage": "build", "progress": 50})
                
                build_proc = await asyncio.create_subprocess_exec(
                    "npm", "run", "build",
                    cwd=str(self.dashboard_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={
                        **os.environ,
                        "VITE_BUILD_OUT": str(self.staging_dir),
                    }
                )
                
                stdout, stderr = await build_proc.communicate()
                
                if build_proc.returncode != 0:
                    return {
                        "status": "error",
                        "error": f"Build failed: {stderr.decode()}",
                    }
                
                # Move build output to staging
                build_output = self.ui_dir / "dist"
                if build_output.exists() and build_output != self.staging_dir:
                    if self.staging_dir.exists():
                        shutil.rmtree(self.staging_dir)
                    shutil.move(str(build_output), str(self.staging_dir))
                
                if on_progress:
                    on_progress({"stage": "complete", "progress": 100})
                
                logger.info("Dashboard build complete")
                
                return {
                    "status": "success",
                    "output_path": str(self.staging_dir),
                    "size_bytes": sum(
                        f.stat().st_size 
                        for f in self.staging_dir.rglob("*") 
                        if f.is_file()
                    ),
                }
            
            except Exception as e:
                logger.error(f"Build error: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                }
    
    async def deploy_staging(
        self,
        version: str | None = None
    ) -> dict[str, Any]:
        """
        Deploy staging build to production (atomic swap).
        
        Args:
            version: Version string (auto-generated if not provided).
        
        Returns:
            Deployment status dict.
        """
        self._ensure_dirs()
        
        if not self.staging_dir.exists() or not any(self.staging_dir.iterdir()):
            return {
                "status": "error",
                "error": "No staging build found. Run build_staging first.",
            }
        
        # Generate version if not provided
        if not version:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            version = f"v0.1.0-{timestamp}"
        
        try:
            # Archive current version if exists
            if self.dist_dir.exists() and any(self.dist_dir.iterdir()):
                current_version = self.get_current_version()
                if current_version:
                    archive_dir = self.versions_dir / current_version
                    if not archive_dir.exists():
                        shutil.copytree(self.dist_dir, archive_dir)
                        logger.info(f"Archived current version to {archive_dir}")
            
            # Atomic swap: rename staging to dist
            if self.dist_dir.exists():
                shutil.rmtree(self.dist_dir)
            
            shutil.move(str(self.staging_dir), str(self.dist_dir))
            
            # Calculate size
            size_bytes = sum(
                f.stat().st_size 
                for f in self.dist_dir.rglob("*") 
                if f.is_file()
            )
            
            # Update manifest
            manifest = self._load_manifest()
            manifest["current_version"] = version
            manifest["versions"].append({
                "version": version,
                "created_at": datetime.utcnow().isoformat(),
                "size_bytes": size_bytes,
            })
            
            # Keep only last 10 versions in manifest
            manifest["versions"] = manifest["versions"][-10:]
            self._save_manifest(manifest)
            
            logger.info(f"Deployed version {version}")
            
            return {
                "status": "success",
                "version": version,
                "size_bytes": size_bytes,
                "deployed_at": datetime.utcnow().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Deployment error: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def rollback_to(self, version: str) -> dict[str, Any]:
        """
        Rollback to a previous version.
        
        Args:
            version: Version string to rollback to.
        
        Returns:
            Rollback status dict.
        """
        version_dir = self.versions_dir / version
        
        if not version_dir.exists():
            return {
                "status": "error",
                "error": f"Version {version} not found",
            }
        
        try:
            # Archive current if not already archived
            current_version = self.get_current_version()
            if current_version and current_version != version:
                current_archive = self.versions_dir / current_version
                if not current_archive.exists() and self.dist_dir.exists():
                    shutil.copytree(self.dist_dir, current_archive)
            
            # Replace dist with version
            if self.dist_dir.exists():
                shutil.rmtree(self.dist_dir)
            
            shutil.copytree(version_dir, self.dist_dir)
            
            # Update manifest
            manifest = self._load_manifest()
            manifest["current_version"] = version
            self._save_manifest(manifest)
            
            logger.info(f"Rolled back to version {version}")
            
            return {
                "status": "success",
                "version": version,
                "rolled_back_from": current_version,
            }
        
        except Exception as e:
            logger.error(f"Rollback error: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def cleanup_old_versions(self, keep: int = 5) -> dict[str, Any]:
        """
        Remove old version archives.
        
        Args:
            keep: Number of recent versions to keep.
        
        Returns:
            Cleanup status dict.
        """
        manifest = self._load_manifest()
        versions = manifest.get("versions", [])
        
        if len(versions) <= keep:
            return {
                "status": "success",
                "removed": 0,
            }
        
        # Keep most recent versions
        versions_to_keep = set(
            v["version"] for v in versions[-keep:]
        )
        versions_to_keep.add(manifest.get("current_version"))
        
        removed = 0
        for version_dir in self.versions_dir.iterdir():
            if version_dir.is_dir() and version_dir.name not in versions_to_keep:
                shutil.rmtree(version_dir)
                removed += 1
                logger.info(f"Removed old version: {version_dir.name}")
        
        return {
            "status": "success",
            "removed": removed,
        }


# Global instance
_version_manager: DashboardVersionManager | None = None


def get_version_manager() -> DashboardVersionManager:
    """Get or create the global version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = DashboardVersionManager()
    return _version_manager
