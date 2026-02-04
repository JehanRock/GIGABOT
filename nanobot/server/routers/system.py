"""
System routes for GigaBot API.

Provides:
- /api/system/status - Get comprehensive system status
- /api/system/health - Lightweight health check
- /api/system/reinitialize - Trigger agent reinitialization
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from nanobot.server.dependencies import AgentManagerDep, ConfigDep

router = APIRouter()


class ReinitializeResponse(BaseModel):
    """Response from reinitialize endpoint."""
    success: bool
    agent_state: str
    message: str


@router.get("/status")
async def get_status(
    request: Request,
    agent_manager: AgentManagerDep,
    config: ConfigDep,
):
    """
    Get comprehensive system status.
    
    Returns:
        - agent_state: Current agent lifecycle state
        - is_ready: Whether agent can handle requests
        - has_api_key: Whether any API key is configured
        - configured_providers: List of providers with keys
        - primary_provider: The active provider
        - version: GigaBot version
        - error: Last error if any
    """
    status = agent_manager.get_status()
    
    # Add config info
    status["model"] = config.agents.defaults.model
    status["workspace"] = str(request.app.state.workspace)
    status["tiered_routing_enabled"] = config.agents.tiered_routing.enabled
    status["memory_enabled"] = config.agents.memory.enabled
    status["swarm_enabled"] = config.agents.swarm.enabled
    
    # Add tracking info if available
    if agent_manager.tracker:
        status["tracking"] = agent_manager.tracker.get_summary()
    
    return JSONResponse(status)


@router.get("/health")
async def health_check():
    """
    Lightweight health check.
    
    Returns simple OK status for load balancers and monitoring.
    """
    return JSONResponse({"status": "ok"})


@router.post("/reinitialize", response_model=ReinitializeResponse)
async def reinitialize(agent_manager: AgentManagerDep):
    """
    Trigger agent reinitialization.
    
    Use after updating provider configuration to apply changes
    without restarting the server.
    """
    success = await agent_manager.reinitialize()
    
    return ReinitializeResponse(
        success=success,
        agent_state=agent_manager.state.value,
        message="Agent reinitialized successfully" if success else agent_manager.get_not_ready_message(),
    )


@router.get("/config")
async def get_config_summary(config: ConfigDep):
    """
    Get sanitized configuration summary.
    
    Does not expose secrets or API keys.
    """
    return JSONResponse({
        "agents": {
            "model": config.agents.defaults.model,
            "max_tokens": config.agents.defaults.max_tokens,
            "max_iterations": config.agents.defaults.max_iterations,
            "tiered_routing": config.agents.tiered_routing.enabled,
        },
        "memory": {
            "enabled": config.agents.memory.enabled,
            "vector_search": config.agents.memory.vector_search,
            "context_memories": config.agents.memory.context_memories,
        },
        "team": {
            "enabled": config.agents.team.enabled,
            "qa_gate_enabled": config.agents.team.qa_gate_enabled,
        },
        "swarm": {
            "enabled": config.agents.swarm.enabled,
            "max_workers": config.agents.swarm.max_workers,
        },
        "security": {
            "auth_mode": config.security.auth.mode,
            "sandbox_mode": config.security.sandbox.mode,
        },
    })
