"""
Configuration routes for GigaBot API.

Provides:
- /api/config/routing - Tiered routing configuration
- /api/config/memory - Memory system configuration
- /api/config/team - Team/swarm configuration
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from nanobot.server.dependencies import ConfigDep, AgentManagerDep
from nanobot.config.loader import persist_config

router = APIRouter()


# =====================
# Routing Configuration
# =====================

class RoutingUpdate(BaseModel):
    """Routing configuration update."""
    enabled: bool | None = None
    fallback_tier: str | None = None


@router.get("/routing")
async def get_routing(config: ConfigDep):
    """Get tiered routing configuration."""
    routing = config.agents.tiered_routing
    return JSONResponse({
        "enabled": routing.enabled,
        "fallback_tier": routing.fallback_tier,
        "tiers": {
            name: {
                "models": tier.models,
                "triggers": tier.triggers,
            }
            for name, tier in routing.tiers.items()
        } if routing.tiers else {},
    })


@router.put("/routing")
async def update_routing(update: RoutingUpdate, config: ConfigDep):
    """Update routing configuration."""
    routing = config.agents.tiered_routing
    
    if update.enabled is not None:
        routing.enabled = update.enabled
    if update.fallback_tier is not None:
        routing.fallback_tier = update.fallback_tier
    
    # Persist config
    try:
        await persist_config(config)
    except Exception as e:
        logger.error(f"Failed to persist config: {e}")
    
    return JSONResponse({
        "success": True,
        "routing": {
            "enabled": routing.enabled,
            "fallback_tier": routing.fallback_tier,
        }
    })


# =====================
# Memory Configuration
# =====================

class MemoryUpdate(BaseModel):
    """Memory configuration update."""
    enabled: bool | None = None
    vector_search: bool | None = None
    context_memories: int | None = None


@router.get("/memory")
async def get_memory_config(config: ConfigDep):
    """Get memory system configuration."""
    memory = config.agents.memory
    return JSONResponse({
        "enabled": memory.enabled,
        "vector_search": memory.vector_search,
        "context_memories": memory.context_memories,
    })


@router.put("/memory")
async def update_memory_config(update: MemoryUpdate, config: ConfigDep):
    """Update memory configuration."""
    memory = config.agents.memory
    
    if update.enabled is not None:
        memory.enabled = update.enabled
    if update.vector_search is not None:
        memory.vector_search = update.vector_search
    if update.context_memories is not None:
        memory.context_memories = update.context_memories
    
    # Persist config
    try:
        await persist_config(config)
    except Exception as e:
        logger.error(f"Failed to persist config: {e}")
    
    return JSONResponse({
        "success": True,
        "memory": {
            "enabled": memory.enabled,
            "vector_search": memory.vector_search,
            "context_memories": memory.context_memories,
        }
    })


# =====================
# Team Configuration
# =====================

class TeamUpdate(BaseModel):
    """Team configuration update."""
    enabled: bool | None = None
    qa_gate_enabled: bool | None = None
    audit_gate_enabled: bool | None = None
    audit_threshold: float | None = None


class SwarmUpdate(BaseModel):
    """Swarm configuration update."""
    enabled: bool | None = None
    max_workers: int | None = None
    worker_model: str | None = None
    orchestrator_model: str | None = None


class TeamSwarmUpdate(BaseModel):
    """Combined team/swarm update."""
    team: TeamUpdate | None = None
    swarm: SwarmUpdate | None = None


@router.get("/team")
async def get_team_config(config: ConfigDep):
    """Get team/swarm configuration."""
    team = config.agents.team
    swarm = config.agents.swarm
    
    return JSONResponse({
        "team": {
            "enabled": team.enabled,
            "qa_gate_enabled": team.qa_gate_enabled,
            "audit_gate_enabled": team.audit_gate_enabled,
            "audit_threshold": team.audit_threshold,
        },
        "swarm": {
            "enabled": swarm.enabled,
            "max_workers": swarm.max_workers,
            "worker_model": swarm.worker_model,
            "orchestrator_model": swarm.orchestrator_model,
        },
    })


@router.put("/team")
async def update_team_config(update: TeamSwarmUpdate, config: ConfigDep):
    """Update team/swarm configuration."""
    if update.team:
        team = config.agents.team
        if update.team.enabled is not None:
            team.enabled = update.team.enabled
        if update.team.qa_gate_enabled is not None:
            team.qa_gate_enabled = update.team.qa_gate_enabled
        if update.team.audit_gate_enabled is not None:
            team.audit_gate_enabled = update.team.audit_gate_enabled
        if update.team.audit_threshold is not None:
            team.audit_threshold = update.team.audit_threshold
    
    if update.swarm:
        swarm = config.agents.swarm
        if update.swarm.enabled is not None:
            swarm.enabled = update.swarm.enabled
        if update.swarm.max_workers is not None:
            swarm.max_workers = update.swarm.max_workers
        if update.swarm.worker_model is not None:
            swarm.worker_model = update.swarm.worker_model
        if update.swarm.orchestrator_model is not None:
            swarm.orchestrator_model = update.swarm.orchestrator_model
    
    # Persist config
    try:
        await persist_config(config)
    except Exception as e:
        logger.error(f"Failed to persist config: {e}")
    
    return JSONResponse({
        "success": True,
        "config": {
            "team": {
                "enabled": config.agents.team.enabled,
                "qa_gate_enabled": config.agents.team.qa_gate_enabled,
            },
            "swarm": {
                "enabled": config.agents.swarm.enabled,
                "max_workers": config.agents.swarm.max_workers,
            },
        }
    })
