"""
Integration tests for Settings API endpoints.

Tests:
- Provider configuration
- Routing configuration
- Memory configuration
- Team configuration
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

# Mock the config before importing
@pytest.fixture
def mock_config():
    """Create a mock config object."""
    from nanobot.config.schema import (
        Config, ProvidersConfig, ProviderConfig, AgentsConfig,
        TieredRoutingConfig, TierConfig, MemoryConfig, TeamConfig,
        SwarmConfig, ChannelsConfig, SecurityConfig, GatewayConfig,
        ToolsConfig, HeartbeatConfig, TokenTrackingConfig, NodesConfig
    )
    
    config = Config(
        providers=ProvidersConfig(
            openrouter=ProviderConfig(api_key="test-key"),
            anthropic=ProviderConfig(api_key=""),
            openai=ProviderConfig(api_key=""),
            moonshot=ProviderConfig(api_base="https://api.moonshot.cn/v1"),
            deepseek=ProviderConfig(api_base="https://api.deepseek.com/v1"),
            glm=ProviderConfig(api_base="https://open.bigmodel.cn/api/paas/v4"),
            qwen=ProviderConfig(api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"),
            ollama=ProviderConfig(api_base="http://localhost:11434/v1"),
            vllm=ProviderConfig(),
        ),
        agents=AgentsConfig(
            tiered_routing=TieredRoutingConfig(
                enabled=True,
                tiers={
                    "tier1": TierConfig(models=["model-a"], triggers=["complex"]),
                    "tier2": TierConfig(models=["model-b"], triggers=["simple"]),
                }
            ),
            memory=MemoryConfig(enabled=True, vector_search=True, context_memories=5),
            team=TeamConfig(enabled=False, qa_gate_enabled=True, audit_gate_enabled=True),
            swarm=SwarmConfig(enabled=False, max_workers=3),
        ),
        channels=ChannelsConfig(),
        security=SecurityConfig(),
        gateway=GatewayConfig(),
        tools=ToolsConfig(),
        heartbeat=HeartbeatConfig(),
        tracking=TokenTrackingConfig(),
        nodes=NodesConfig(),
    )
    return config


@pytest.fixture
def api_routes(mock_config):
    """Create API routes with mock config."""
    from nanobot.ui.api import create_api_routes
    
    save_config_mock = MagicMock()
    routes = create_api_routes(
        config=mock_config,
        save_config=save_config_mock,
    )
    routes['_save_config_mock'] = save_config_mock
    return routes


class TestProvidersAPI:
    """Tests for provider configuration endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_providers_returns_all_providers(self, api_routes):
        """Test that get_providers returns all configured providers."""
        result = await api_routes['providers']()
        
        assert 'providers' in result
        assert 'openrouter' in result['providers']
        assert 'anthropic' in result['providers']
        assert 'moonshot' in result['providers']
    
    @pytest.mark.asyncio
    async def test_get_providers_shows_has_key_status(self, api_routes):
        """Test that has_key reflects actual API key presence."""
        result = await api_routes['providers']()
        
        # openrouter has a key in mock config
        assert result['providers']['openrouter']['has_key'] is True
        # anthropic doesn't have a key
        assert result['providers']['anthropic']['has_key'] is False
    
    @pytest.mark.asyncio
    async def test_update_provider_sets_api_key(self, api_routes):
        """Test updating a provider's API key."""
        result = await api_routes['update_provider'](
            'anthropic', 
            {'api_key': 'new-test-key'}
        )
        
        assert result['success'] is True
        assert result['provider'] == 'anthropic'
        assert result['has_key'] is True
        
        # Verify save was called
        api_routes['_save_config_mock'].assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_provider_unknown_provider(self, api_routes):
        """Test updating an unknown provider returns error."""
        result = await api_routes['update_provider'](
            'unknown_provider',
            {'api_key': 'test'}
        )
        
        assert 'error' in result
        assert 'Unknown provider' in result['error']


class TestRoutingAPI:
    """Tests for routing configuration endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_routing_returns_config(self, api_routes):
        """Test that get_routing returns routing configuration."""
        result = await api_routes['routing']()
        
        assert 'enabled' in result
        assert 'tiers' in result
        assert result['enabled'] is True
    
    @pytest.mark.asyncio
    async def test_get_routing_includes_tiers(self, api_routes):
        """Test that routing config includes tier details."""
        result = await api_routes['routing']()
        
        assert 'tier1' in result['tiers']
        assert 'models' in result['tiers']['tier1']
        assert 'triggers' in result['tiers']['tier1']
    
    @pytest.mark.asyncio
    async def test_update_routing_enabled(self, api_routes):
        """Test toggling routing enabled state."""
        result = await api_routes['update_routing']({'enabled': False})
        
        assert result['success'] is True
        assert result['routing']['enabled'] is False
        api_routes['_save_config_mock'].assert_called()
    
    @pytest.mark.asyncio
    async def test_update_routing_tier_models(self, api_routes):
        """Test updating tier models."""
        result = await api_routes['update_routing']({
            'tiers': {
                'tier1': {'models': ['new-model-x', 'new-model-y']}
            }
        })
        
        assert result['success'] is True
        assert 'new-model-x' in result['routing']['tiers']['tier1']['models']


class TestMemoryAPI:
    """Tests for memory configuration endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_memory_config(self, api_routes):
        """Test getting memory configuration."""
        result = await api_routes['memory_config']()
        
        assert 'enabled' in result
        assert 'vector_search' in result
        assert 'context_memories' in result
    
    @pytest.mark.asyncio
    async def test_get_memory_config_values(self, api_routes):
        """Test memory config has correct values."""
        result = await api_routes['memory_config']()
        
        assert result['enabled'] is True
        assert result['vector_search'] is True
        assert result['context_memories'] == 5
    
    @pytest.mark.asyncio
    async def test_update_memory_config(self, api_routes):
        """Test updating memory configuration."""
        result = await api_routes['update_memory_config']({
            'enabled': False,
            'context_memories': 10
        })
        
        assert result['success'] is True
        assert result['memory']['enabled'] is False
        assert result['memory']['context_memories'] == 10


class TestTeamAPI:
    """Tests for team configuration endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_team_config(self, api_routes):
        """Test getting team configuration."""
        result = await api_routes['team_config']()
        
        assert 'team' in result
        assert 'swarm' in result
    
    @pytest.mark.asyncio
    async def test_get_team_config_structure(self, api_routes):
        """Test team config has correct structure."""
        result = await api_routes['team_config']()
        
        assert 'enabled' in result['team']
        assert 'qa_gate_enabled' in result['team']
        assert 'audit_gate_enabled' in result['team']
        assert 'max_workers' in result['swarm']
    
    @pytest.mark.asyncio
    async def test_update_team_config(self, api_routes):
        """Test updating team configuration."""
        result = await api_routes['update_team_config']({
            'team': {'enabled': True, 'qa_gate_enabled': False},
            'swarm': {'max_workers': 5}
        })
        
        assert result['success'] is True
        assert result['config']['team']['enabled'] is True
        assert result['config']['team']['qa_gate_enabled'] is False
        assert result['config']['swarm']['max_workers'] == 5


class TestConfigPersistence:
    """Tests for configuration persistence."""
    
    @pytest.mark.asyncio
    async def test_save_called_on_provider_update(self, api_routes):
        """Test that save_config is called when provider is updated."""
        await api_routes['update_provider']('openai', {'api_key': 'test'})
        api_routes['_save_config_mock'].assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_called_on_routing_update(self, api_routes):
        """Test that save_config is called when routing is updated."""
        await api_routes['update_routing']({'enabled': True})
        api_routes['_save_config_mock'].assert_called()
    
    @pytest.mark.asyncio
    async def test_save_called_on_memory_update(self, api_routes):
        """Test that save_config is called when memory config is updated."""
        await api_routes['update_memory_config']({'vector_search': False})
        api_routes['_save_config_mock'].assert_called()
    
    @pytest.mark.asyncio
    async def test_save_called_on_team_update(self, api_routes):
        """Test that save_config is called when team config is updated."""
        await api_routes['update_team_config']({'team': {'enabled': True}})
        api_routes['_save_config_mock'].assert_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
