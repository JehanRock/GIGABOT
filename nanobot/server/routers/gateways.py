"""
Gateway routes for GigaBot API.

Provides:
- /api/gateways - List and manage LLM gateways
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
import httpx

from nanobot.server.dependencies import ConfigDep, AgentManagerDep
from nanobot.config.loader import persist_config
from nanobot.config.schema import LLMGatewayConfig

router = APIRouter()


class GatewayCreate(BaseModel):
    """Gateway creation request."""
    name: str
    provider: str = "openrouter"
    api_key: str = ""
    api_base: str | None = None
    enabled: bool = True
    is_primary: bool = False
    is_fallback: bool = False
    priority: int | None = None


class GatewayUpdate(BaseModel):
    """Gateway update request."""
    name: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    enabled: bool | None = None
    is_primary: bool | None = None
    is_fallback: bool | None = None
    priority: int | None = None


@router.get("")
async def list_gateways(config: ConfigDep):
    """List all configured gateways."""
    gateways = config.providers.gateways.gateways
    return JSONResponse({
        "gateways": [
            {
                "id": g.id,
                "name": g.name,
                "provider": g.provider,
                "enabled": g.enabled,
                "is_primary": g.is_primary,
                "is_fallback": g.is_fallback,
                "priority": g.priority,
                "health_status": g.health_status,
                "last_error": g.last_error,
                "failure_count": g.failure_count,
                "has_api_key": bool(g.api_key),
                "api_base": g.api_base,
            }
            for g in gateways
        ],
        "cooldown_seconds": config.providers.gateways.cooldown_seconds,
        "max_retries": config.providers.gateways.max_retries,
    })


@router.post("")
async def create_gateway(gateway: GatewayCreate, config: ConfigDep):
    """Create a new gateway."""
    # Generate unique ID
    gateway_id = str(uuid.uuid4())[:8]
    
    # If this is set as primary, unset any existing primary
    if gateway.is_primary:
        for g in config.providers.gateways.gateways:
            g.is_primary = False
    
    new_gateway = LLMGatewayConfig(
        id=gateway_id,
        name=gateway.name,
        provider=gateway.provider,
        api_key=gateway.api_key,
        api_base=gateway.api_base,
        enabled=gateway.enabled,
        is_primary=gateway.is_primary,
        is_fallback=gateway.is_fallback,
        priority=gateway.priority or len(config.providers.gateways.gateways),
        health_status="unknown",
    )
    
    config.providers.gateways.gateways.append(new_gateway)
    
    # Persist config
    try:
        await persist_config(config)
    except Exception as e:
        logger.error(f"Failed to persist config: {e}")
    
    return JSONResponse({
        "success": True,
        "gateway": {
            "id": new_gateway.id,
            "name": new_gateway.name,
            "provider": new_gateway.provider,
            "enabled": new_gateway.enabled,
            "is_primary": new_gateway.is_primary,
        }
    }, status_code=201)


@router.get("/{gateway_id}")
async def get_gateway(gateway_id: str, config: ConfigDep):
    """Get specific gateway configuration."""
    for g in config.providers.gateways.gateways:
        if g.id == gateway_id:
            return JSONResponse({
                "id": g.id,
                "name": g.name,
                "provider": g.provider,
                "enabled": g.enabled,
                "is_primary": g.is_primary,
                "is_fallback": g.is_fallback,
                "priority": g.priority,
                "health_status": g.health_status,
                "has_api_key": bool(g.api_key),
                "api_base": g.api_base,
            })
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Gateway not found: {gateway_id}",
    )


@router.put("/{gateway_id}")
async def update_gateway(gateway_id: str, update: GatewayUpdate, config: ConfigDep):
    """Update gateway configuration."""
    gateway = None
    for g in config.providers.gateways.gateways:
        if g.id == gateway_id:
            gateway = g
            break
    
    if not gateway:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway not found: {gateway_id}",
        )
    
    # If setting as primary, unset any existing primary
    if update.is_primary and not gateway.is_primary:
        for g in config.providers.gateways.gateways:
            g.is_primary = False
    
    # Update fields
    if update.name is not None:
        gateway.name = update.name
    if update.api_key is not None:
        gateway.api_key = update.api_key
    if update.api_base is not None:
        gateway.api_base = update.api_base
    if update.enabled is not None:
        gateway.enabled = update.enabled
    if update.is_primary is not None:
        gateway.is_primary = update.is_primary
    if update.is_fallback is not None:
        gateway.is_fallback = update.is_fallback
    if update.priority is not None:
        gateway.priority = update.priority
    
    # Persist config
    try:
        await persist_config(config)
    except Exception as e:
        logger.error(f"Failed to persist config: {e}")
    
    return JSONResponse({
        "success": True,
        "gateway": {
            "id": gateway.id,
            "name": gateway.name,
            "provider": gateway.provider,
            "enabled": gateway.enabled,
            "is_primary": gateway.is_primary,
        }
    })


@router.delete("/{gateway_id}")
async def delete_gateway(gateway_id: str, config: ConfigDep):
    """Delete a gateway."""
    gateways = config.providers.gateways.gateways
    for i, g in enumerate(gateways):
        if g.id == gateway_id:
            del gateways[i]
            
            # Persist config
            try:
                await persist_config(config)
            except Exception as e:
                logger.error(f"Failed to persist config: {e}")
            
            return JSONResponse({"success": True, "deleted_id": gateway_id})
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Gateway not found: {gateway_id}",
    )


@router.post("/{gateway_id}/test")
async def test_gateway(gateway_id: str, config: ConfigDep):
    """Test gateway connectivity."""
    gateway = None
    for g in config.providers.gateways.gateways:
        if g.id == gateway_id:
            gateway = g
            break
    
    if not gateway:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway not found: {gateway_id}",
        )
    
    if not gateway.api_key:
        return JSONResponse({
            "success": False,
            "error": "Gateway has no API key configured",
        })
    
    # Test connectivity
    api_bases = {
        "openrouter": "https://openrouter.ai/api/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "openai": "https://api.openai.com/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }
    
    api_base = gateway.api_base or api_bases.get(gateway.provider, "https://api.openai.com/v1")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {gateway.api_key}",
                "Content-Type": "application/json",
            }
            
            if gateway.provider == "anthropic":
                headers["x-api-key"] = gateway.api_key
                headers["anthropic-version"] = "2023-06-01"
                url = f"{api_base}/messages"
                response = await client.post(
                    url,
                    headers=headers,
                    json={"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": []}
                )
                if response.status_code in [200, 400]:
                    gateway.health_status = "healthy"
                    gateway.failure_count = 0
                    gateway.last_error = None
                    return JSONResponse({"success": True, "status": "healthy"})
                elif response.status_code == 401:
                    gateway.health_status = "unhealthy"
                    gateway.last_error = "Invalid API key"
                    return JSONResponse({"success": False, "error": "Invalid API key"})
            else:
                url = f"{api_base}/models"
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    gateway.health_status = "healthy"
                    gateway.failure_count = 0
                    gateway.last_error = None
                    return JSONResponse({"success": True, "status": "healthy"})
                else:
                    gateway.health_status = "unhealthy"
                    gateway.last_error = f"HTTP {response.status_code}"
                    return JSONResponse({"success": False, "error": f"HTTP {response.status_code}"})
    
    except httpx.TimeoutException:
        gateway.health_status = "unhealthy"
        gateway.last_error = "Connection timeout"
        return JSONResponse({"success": False, "error": "Connection timeout"})
    except Exception as e:
        gateway.health_status = "unhealthy"
        gateway.last_error = str(e)
        return JSONResponse({"success": False, "error": str(e)})
