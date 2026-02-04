"""
FastAPI middleware for GigaBot.

Provides:
- Cookie-based authentication
- Request logging
- Error handling
"""

from nanobot.server.middleware.auth import AuthMiddleware, get_current_session

__all__ = ["AuthMiddleware", "get_current_session"]
