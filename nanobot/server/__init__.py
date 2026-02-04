"""
GigaBot Server Module.

Provides FastAPI-based web server with:
- REST API endpoints for system, chat, config management
- WebSocket support for streaming chat
- Agent lifecycle management with hot-reload
- Cookie-based authentication
"""

from nanobot.server.agent_manager import AgentManager, AgentState

__all__ = ["AgentManager", "AgentState"]
