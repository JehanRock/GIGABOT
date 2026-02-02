"""
Daemon manager for GigaBot.

Handles service installation and management across platforms.
"""

import os
import sys
import subprocess
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from loguru import logger


class DaemonStatus(str, Enum):
    """Status of the daemon service."""
    NOT_INSTALLED = "not_installed"
    STOPPED = "stopped"
    RUNNING = "running"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class DaemonConfig:
    """Configuration for the daemon service."""
    service_name: str = "gigabot"
    description: str = "GigaBot AI Assistant"
    user: str = ""  # Run as specific user
    start_on_boot: bool = True
    restart_on_failure: bool = True
    working_directory: str = ""


class DaemonManager:
    """
    Manages GigaBot as a system service.
    
    Supports:
    - Linux (systemd)
    - macOS (launchd)
    - Windows (Task Scheduler)
    """
    
    def __init__(self, config: DaemonConfig | None = None):
        self.config = config or DaemonConfig()
        self.platform = sys.platform
    
    def install(self) -> bool:
        """
        Install GigaBot as a system service.
        
        Returns:
            True if installation successful.
        """
        if self.platform.startswith("linux"):
            return self._install_systemd()
        elif self.platform == "darwin":
            return self._install_launchd()
        elif self.platform == "win32":
            return self._install_windows()
        else:
            logger.error(f"Unsupported platform: {self.platform}")
            return False
    
    def uninstall(self) -> bool:
        """
        Uninstall the system service.
        
        Returns:
            True if uninstallation successful.
        """
        if self.platform.startswith("linux"):
            return self._uninstall_systemd()
        elif self.platform == "darwin":
            return self._uninstall_launchd()
        elif self.platform == "win32":
            return self._uninstall_windows()
        else:
            return False
    
    def status(self) -> DaemonStatus:
        """Get the current service status."""
        if self.platform.startswith("linux"):
            return self._status_systemd()
        elif self.platform == "darwin":
            return self._status_launchd()
        elif self.platform == "win32":
            return self._status_windows()
        else:
            return DaemonStatus.UNKNOWN
    
    def start(self) -> bool:
        """Start the service."""
        if self.platform.startswith("linux"):
            return self._run_cmd(["systemctl", "start", self.config.service_name])
        elif self.platform == "darwin":
            return self._run_cmd(["launchctl", "load", "-w", self._launchd_plist_path()])
        elif self.platform == "win32":
            return self._run_cmd(["schtasks", "/run", "/tn", self.config.service_name])
        return False
    
    def stop(self) -> bool:
        """Stop the service."""
        if self.platform.startswith("linux"):
            return self._run_cmd(["systemctl", "stop", self.config.service_name])
        elif self.platform == "darwin":
            return self._run_cmd(["launchctl", "unload", self._launchd_plist_path()])
        elif self.platform == "win32":
            return self._run_cmd(["schtasks", "/end", "/tn", self.config.service_name])
        return False
    
    def restart(self) -> bool:
        """Restart the service."""
        if self.platform.startswith("linux"):
            return self._run_cmd(["systemctl", "restart", self.config.service_name])
        elif self.platform == "darwin":
            self.stop()
            return self.start()
        elif self.platform == "win32":
            self.stop()
            return self.start()
        return False
    
    def logs(self, lines: int = 50) -> str:
        """Get recent service logs."""
        if self.platform.startswith("linux"):
            result = subprocess.run(
                ["journalctl", "-u", self.config.service_name, "-n", str(lines), "--no-pager"],
                capture_output=True,
                text=True,
            )
            return result.stdout
        elif self.platform == "darwin":
            log_path = Path.home() / "Library" / "Logs" / f"{self.config.service_name}.log"
            if log_path.exists():
                return log_path.read_text()[-10000:]  # Last 10KB
            return "No logs found"
        elif self.platform == "win32":
            return "Use Event Viewer for Windows logs"
        return ""
    
    # ========== Linux (systemd) ==========
    
    def _install_systemd(self) -> bool:
        """Install systemd service."""
        service_file = self._systemd_service_path()
        
        # Create service file content
        content = f"""[Unit]
Description={self.config.description}
After=network.target

[Service]
Type=simple
ExecStart={sys.executable} -m nanobot gateway
WorkingDirectory={self.config.working_directory or str(Path.home())}
Restart={'always' if self.config.restart_on_failure else 'no'}
RestartSec=10
{f"User={self.config.user}" if self.config.user else ""}

[Install]
WantedBy=multi-user.target
"""
        
        try:
            # Write service file (requires sudo)
            service_file.write_text(content)
            
            # Reload systemd
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            
            # Enable on boot
            if self.config.start_on_boot:
                subprocess.run(["systemctl", "enable", self.config.service_name], check=True)
            
            logger.info(f"Installed systemd service: {service_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to install systemd service: {e}")
            return False
    
    def _uninstall_systemd(self) -> bool:
        """Uninstall systemd service."""
        try:
            # Stop service
            subprocess.run(["systemctl", "stop", self.config.service_name], check=False)
            
            # Disable
            subprocess.run(["systemctl", "disable", self.config.service_name], check=False)
            
            # Remove file
            service_file = self._systemd_service_path()
            if service_file.exists():
                service_file.unlink()
            
            # Reload
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall systemd service: {e}")
            return False
    
    def _status_systemd(self) -> DaemonStatus:
        """Get systemd service status."""
        result = subprocess.run(
            ["systemctl", "is-active", self.config.service_name],
            capture_output=True,
            text=True,
        )
        
        status = result.stdout.strip()
        if status == "active":
            return DaemonStatus.RUNNING
        elif status == "inactive":
            return DaemonStatus.STOPPED
        elif status == "failed":
            return DaemonStatus.FAILED
        elif "could not be found" in result.stderr:
            return DaemonStatus.NOT_INSTALLED
        return DaemonStatus.UNKNOWN
    
    def _systemd_service_path(self) -> Path:
        """Get systemd service file path."""
        return Path(f"/etc/systemd/system/{self.config.service_name}.service")
    
    # ========== macOS (launchd) ==========
    
    def _install_launchd(self) -> bool:
        """Install launchd service."""
        plist_path = Path(self._launchd_plist_path())
        
        # Create plist content
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{self.config.service_name}.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>-m</string>
        <string>nanobot</string>
        <string>gateway</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{self.config.working_directory or str(Path.home())}</string>
    <key>RunAtLoad</key>
    <{'true' if self.config.start_on_boot else 'false'}/>
    <key>KeepAlive</key>
    <{('true' if self.config.restart_on_failure else 'false')}/>
    <key>StandardOutPath</key>
    <string>{Path.home() / 'Library' / 'Logs' / f'{self.config.service_name}.log'}</string>
    <key>StandardErrorPath</key>
    <string>{Path.home() / 'Library' / 'Logs' / f'{self.config.service_name}.error.log'}</string>
</dict>
</plist>
"""
        
        try:
            plist_path.write_text(content)
            logger.info(f"Installed launchd service: {plist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to install launchd service: {e}")
            return False
    
    def _uninstall_launchd(self) -> bool:
        """Uninstall launchd service."""
        try:
            plist_path = Path(self._launchd_plist_path())
            
            # Unload
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
            
            # Remove file
            if plist_path.exists():
                plist_path.unlink()
            
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall launchd service: {e}")
            return False
    
    def _status_launchd(self) -> DaemonStatus:
        """Get launchd service status."""
        plist_path = Path(self._launchd_plist_path())
        
        if not plist_path.exists():
            return DaemonStatus.NOT_INSTALLED
        
        result = subprocess.run(
            ["launchctl", "list", f"com.{self.config.service_name}.agent"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            return DaemonStatus.RUNNING
        return DaemonStatus.STOPPED
    
    def _launchd_plist_path(self) -> str:
        """Get launchd plist path."""
        return str(Path.home() / "Library" / "LaunchAgents" / f"com.{self.config.service_name}.agent.plist")
    
    # ========== Windows (Task Scheduler) ==========
    
    def _install_windows(self) -> bool:
        """Install Windows scheduled task."""
        xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{self.config.description}</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>{'true' if self.config.start_on_boot else 'false'}</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{sys.executable}</Command>
      <Arguments>-m nanobot gateway</Arguments>
      <WorkingDirectory>{self.config.working_directory or str(Path.home())}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
        
        try:
            # Write XML file
            xml_path = Path.home() / f"{self.config.service_name}-task.xml"
            xml_path.write_text(xml_content, encoding="utf-16")
            
            # Create task
            result = subprocess.run(
                ["schtasks", "/create", "/tn", self.config.service_name, "/xml", str(xml_path), "/f"],
                capture_output=True,
                text=True,
            )
            
            # Clean up XML
            xml_path.unlink()
            
            if result.returncode == 0:
                logger.info(f"Installed Windows task: {self.config.service_name}")
                return True
            else:
                logger.error(f"Failed to create task: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to install Windows task: {e}")
            return False
    
    def _uninstall_windows(self) -> bool:
        """Uninstall Windows scheduled task."""
        try:
            result = subprocess.run(
                ["schtasks", "/delete", "/tn", self.config.service_name, "/f"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to uninstall Windows task: {e}")
            return False
    
    def _status_windows(self) -> DaemonStatus:
        """Get Windows task status."""
        result = subprocess.run(
            ["schtasks", "/query", "/tn", self.config.service_name, "/fo", "list"],
            capture_output=True,
            text=True,
        )
        
        if "ERROR" in result.stderr or result.returncode != 0:
            return DaemonStatus.NOT_INSTALLED
        
        if "Running" in result.stdout:
            return DaemonStatus.RUNNING
        return DaemonStatus.STOPPED
    
    # ========== Helpers ==========
    
    def _run_cmd(self, cmd: list[str]) -> bool:
        """Run a command and return success."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False
    
    def get_info(self) -> dict[str, Any]:
        """Get daemon information."""
        return {
            "platform": self.platform,
            "service_name": self.config.service_name,
            "status": self.status().value,
            "start_on_boot": self.config.start_on_boot,
        }


# Global instance
_daemon_manager: DaemonManager | None = None


def get_daemon_manager() -> DaemonManager:
    """Get the global daemon manager."""
    global _daemon_manager
    if _daemon_manager is None:
        _daemon_manager = DaemonManager()
    return _daemon_manager
