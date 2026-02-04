"""
Provider routes for GigaBot API.

Provides:
- /api/providers - List configured providers
- /api/providers/{name} - Update provider configuration
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from nanobot.server.dependencies import AgentManagerDep, ConfigDep
from nanobot.config.loader import persist_config

router = APIRouter()


# Supported providers
SUPPORTED_PROVIDERS = [
    "openrouter",
    "anthropic", 
    "openai",
    "moonshot",
    "deepseek",
    "glm",
    "qwen",
    "ollama",
    "vllm",
]


class ProviderInfo(BaseModel):
    """Provider information."""
    name: str
    has_key: bool
    api_base: str | None
    is_primary: bool


class ProviderUpdate(BaseModel):
    """Provider update request."""
    api_key: str | None = None
    api_base: str | None = None


class ProviderUpdateResponse(BaseModel):
    """Provider update response."""
    success: bool
    provider: str
    has_key: bool
    agent_state: str
    message: str


@router.get("")
async def list_providers(config: ConfigDep, agent_manager: AgentManagerDep):
    """
    List all providers with their configuration status.
    
    API keys are masked - only shows whether configured.
    """
    providers_info = {}
    primary_provider = agent_manager._get_primary_provider()
    
    for name in SUPPORTED_PROVIDERS:
        provider_config = getattr(config.providers, name, None)
        if provider_config:
            providers_info[name] = {
                "has_key": bool(provider_config.api_key),
                "api_base": provider_config.api_base,
                "is_primary": name == primary_provider,
            }
    
    return JSONResponse({
        "providers": providers_info,
        "primary": primary_provider,
        "configured_count": len([p for p in providers_info.values() if p["has_key"]]),
    })


@router.get("/{provider_name}")
async def get_provider(provider_name: str, config: ConfigDep, agent_manager: AgentManagerDep):
    """Get specific provider configuration."""
    if provider_name not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown provider: {provider_name}",
        )
    
    provider_config = getattr(config.providers, provider_name, None)
    if not provider_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider not found: {provider_name}",
        )
    
    primary_provider = agent_manager._get_primary_provider()
    
    return JSONResponse({
        "name": provider_name,
        "has_key": bool(provider_config.api_key),
        "api_base": provider_config.api_base,
        "is_primary": provider_name == primary_provider,
    })


@router.put("/{provider_name}", response_model=ProviderUpdateResponse)
async def update_provider(
    provider_name: str,
    update: ProviderUpdate,
    config: ConfigDep,
    agent_manager: AgentManagerDep,
):
    """
    Update provider configuration.
    
    After updating, automatically triggers agent reinitialization
    to apply the new configuration.
    """
    if provider_name not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown provider: {provider_name}",
        )
    
    provider_config = getattr(config.providers, provider_name, None)
    if not provider_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider not found: {provider_name}",
        )
    
    # Update fields
    if update.api_key is not None:
        provider_config.api_key = update.api_key
        logger.info(f"Updated API key for provider: {provider_name}")
    
    if update.api_base is not None:
        provider_config.api_base = update.api_base
        logger.info(f"Updated API base for provider: {provider_name}")
    
    # Persist config to disk
    try:
        await persist_config(config)
        logger.info("Configuration persisted to disk")
    except Exception as e:
        logger.error(f"Failed to persist config: {e}")
        # Continue anyway - in-memory config is updated
    
    # Reinitialize agent to use new config
    success = await agent_manager.reinitialize()
    
    return ProviderUpdateResponse(
        success=success,
        provider=provider_name,
        has_key=bool(provider_config.api_key),
        agent_state=agent_manager.state.value,
        message="Provider updated and agent reinitialized" if success else agent_manager.get_not_ready_message(),
    )


@router.post("/{provider_name}/test")
async def test_provider(provider_name: str, config: ConfigDep):
    """
    Test provider connectivity.
    
    Attempts to make a simple API call to verify the key works.
    """
    if provider_name not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown provider: {provider_name}",
        )
    
    provider_config = getattr(config.providers, provider_name, None)
    if not provider_config or not provider_config.api_key:
        return JSONResponse({
            "success": False,
            "error": "No API key configured",
        })
    
    # Test connectivity
    import httpx
    
    api_bases = {
        "openrouter": "https://openrouter.ai/api/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "openai": "https://api.openai.com/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "glm": "https://open.bigmodel.cn/api/paas/v4",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "ollama": "http://localhost:11434/v1",
        "vllm": "http://localhost:8000/v1",
    }
    
    api_base = provider_config.api_base or api_bases.get(provider_name, "https://api.openai.com/v1")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {provider_config.api_key}",
                "Content-Type": "application/json",
            }
            
            if provider_name == "anthropic":
                # Anthropic uses different auth header
                headers["x-api-key"] = provider_config.api_key
                headers["anthropic-version"] = "2023-06-01"
                url = f"{api_base}/messages"
                response = await client.post(
                    url,
                    headers=headers,
                    json={"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": []}
                )
                # 400 (bad request) means key works, 401 means invalid
                if response.status_code in [200, 400]:
                    return JSONResponse({"success": True, "status": "healthy"})
                elif response.status_code == 401:
                    return JSONResponse({"success": False, "error": "Invalid API key"})
            else:
                # Try models endpoint
                url = f"{api_base}/models"
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    return JSONResponse({"success": True, "status": "healthy"})
                else:
                    return JSONResponse({
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                    })
    
    except httpx.TimeoutException:
        return JSONResponse({"success": False, "error": "Connection timeout"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
