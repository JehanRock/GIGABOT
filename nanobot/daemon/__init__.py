"""
Daemon service for GigaBot.

Run GigaBot as a system service:
- systemd (Linux)
- launchd (macOS)
- Task Scheduler (Windows)
"""

from nanobot.daemon.manager import (
    DaemonManager,
    DaemonStatus,
    get_daemon_manager,
)

__all__ = [
    "DaemonManager",
    "DaemonStatus",
    "get_daemon_manager",
]
