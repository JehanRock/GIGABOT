"""
WebUI dashboard for GigaBot.

Provides:
- HTTP API server
- WebSocket for real-time updates
- Static file serving for dashboard
"""

from nanobot.ui.server import (
    UIServer,
    start_server,
)
from nanobot.ui.api import (
    create_api_routes,
)

__all__ = [
    "UIServer",
    "start_server",
    "create_api_routes",
]
