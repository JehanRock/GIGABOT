"""
FastAPI dependency injection utilities.

Provides dependencies for:
- Config access
- Agent manager access
- Authentication
"""

from typing import TYPE_CHECKING, Annotated
from fastapi import Depends, Request, HTTPException, status

if TYPE_CHECKING:
    from nanobot.config.schema import Config
    from nanobot.server.agent_manager import AgentManager


def get_config(request: Request) -> "Config":
    """Get config from app state."""
    return request.app.state.config


def get_agent_manager(request: Request) -> "AgentManager":
    """Get agent manager from app state."""
    return request.app.state.agent_manager


def get_workspace(request: Request):
    """Get workspace path from app state."""
    return request.app.state.workspace


# Type aliases for dependency injection
ConfigDep = Annotated["Config", Depends(get_config)]
AgentManagerDep = Annotated["AgentManager", Depends(get_agent_manager)]


async def require_ready_agent(
    agent_manager: AgentManagerDep,
) -> "AgentManager":
    """Dependency that requires agent to be ready."""
    if not agent_manager.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Agent not ready",
                "agent_state": agent_manager.state.value,
                "message": agent_manager.get_not_ready_message(),
            }
        )
    return agent_manager


ReadyAgentDep = Annotated["AgentManager", Depends(require_ready_agent)]
