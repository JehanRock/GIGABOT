"""
FastAPI routers for GigaBot API.

Provides modular route organization:
- system: Status, health, reinitialize
- chat: Messages and WebSocket streaming
- config: Configuration management
- providers: LLM provider configuration
- gateways: Gateway management
"""

from nanobot.server.routers.system import router as system_router
from nanobot.server.routers.chat import router as chat_router
from nanobot.server.routers.providers import router as providers_router
from nanobot.server.routers.config import router as config_router
from nanobot.server.routers.gateways import router as gateways_router

__all__ = [
    "system_router",
    "chat_router",
    "providers_router",
    "config_router",
    "gateways_router",
]
