"""
WebUI dashboard for GigaBot.

Provides:
- HTTP API server
- WebSocket for real-time updates
- Static file serving for dashboard
- Version management for hot-swap deployments
"""

from nanobot.ui.server import (
    UIServer,
    start_server,
)
from nanobot.ui.api import (
    create_api_routes,
)
from nanobot.ui.versions import (
    DashboardVersionManager,
    get_version_manager,
)

__all__ = [
    "UIServer",
    "start_server",
    "create_api_routes",
    "DashboardVersionManager",
    "get_version_manager",
]
