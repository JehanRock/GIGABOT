"""
Integration tests for FastAPI server endpoints.

Tests:
- System status endpoint
- Provider management
- Chat availability gating
- Agent state transitions
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Skip if fastapi not installed
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.fixture
def mock_config():
    """Create a mock config object."""
    config = Mock()
    
    # Providers
    config.providers = Mock()
    config.providers.openrouter = Mock(api_key="", api_base=None)
    config.providers.anthropic = Mock(api_key="", api_base=None)
    config.providers.openai = Mock(api_key="", api_base=None)
    config.providers.moonshot = Mock(api_key="", api_base=None)
    config.providers.deepseek = Mock(api_key="", api_base=None)
    config.providers.glm = Mock(api_key="", api_base=None)
    config.providers.qwen = Mock(api_key="", api_base=None)
    config.providers.ollama = Mock(api_key="", api_base=None)
    config.providers.vllm = Mock(api_key="", api_base=None)
    config.providers.gateways = Mock(gateways=[], cooldown_seconds=60, max_retries=3)
    
    # Agents config
    config.agents = Mock()
    config.agents.defaults = Mock(model="moonshot/kimi-k2.5", max_tokens=4096, max_iterations=10)
    config.agents.tiered_routing = Mock(enabled=True, fallback_tier="tier2", tiers={})
    config.agents.memory = Mock(enabled=True, vector_search=True, context_memories=5)
    config.agents.team = Mock(enabled=False, qa_gate_enabled=True, audit_gate_enabled=True, audit_threshold=0.8)
    config.agents.swarm = Mock(enabled=False, max_workers=3, worker_model="", orchestrator_model="")
    
    # Security
    config.security = Mock()
    config.security.auth = Mock(mode="none", password_hash="", password_salt="", pin_hash="", pin_salt="", require_pin=False, session_duration_days=7)
    config.security.sandbox = Mock(mode="off")
    
    # Other
    config.workspace_path = Path("/tmp/test-workspace")
    config.nodes = Mock(enabled=False)
    config.get_api_key = Mock(return_value=None)
    config.get_api_base = Mock(return_value=None)
    
    return config


@pytest.fixture
def app(mock_config):
    """Create FastAPI app with mock config."""
    from nanobot.server.main import create_app
    
    app = create_app(
        config=mock_config,
        workspace=mock_config.workspace_path,
    )
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestSystemEndpoints:
    """Test /api/system/* endpoints."""
    
    def test_health_check(self, client):
        """Test health endpoint returns OK."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_system_status_uninitialized(self, client):
        """Test system status shows uninitialized when no API key."""
        response = client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["agent_state"] == "uninitialized"
        assert data["is_ready"] == False
        assert data["has_api_key"] == False
        assert data["configured_providers"] == []
    
    def test_system_config(self, client):
        """Test system config endpoint returns sanitized config."""
        response = client.get("/api/system/config")
        assert response.status_code == 200
        data = response.json()
        
        assert "agents" in data
        assert "memory" in data
        assert "team" in data
        assert "security" in data
        # Should not contain API keys
        assert "api_key" not in str(data)


class TestProviderEndpoints:
    """Test /api/providers/* endpoints."""
    
    def test_list_providers(self, client):
        """Test listing providers."""
        response = client.get("/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        assert "providers" in data
        assert "openrouter" in data["providers"]
        assert data["providers"]["openrouter"]["has_key"] == False
    
    def test_get_provider(self, client):
        """Test getting single provider."""
        response = client.get("/api/providers/openrouter")
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "openrouter"
        assert data["has_key"] == False
    
    def test_get_unknown_provider(self, client):
        """Test getting unknown provider returns 404."""
        response = client.get("/api/providers/unknown")
        assert response.status_code == 404
    
    def test_update_provider(self, client, mock_config):
        """Test updating provider API key."""
        response = client.put(
            "/api/providers/openrouter",
            json={"api_key": "sk-test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["provider"] == "openrouter"
        # API key should be updated in config
        assert mock_config.providers.openrouter.api_key == "sk-test-key"


class TestChatEndpoints:
    """Test /api/chat/* endpoints."""
    
    def test_chat_status_not_ready(self, client):
        """Test chat status when agent not ready."""
        response = client.get("/api/chat/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["available"] == False
        assert data["agent_state"] == "uninitialized"
        assert data["message"] is not None
    
    def test_chat_without_api_key(self, client):
        """Test chat endpoint rejects when no API key."""
        response = client.post(
            "/api/chat",
            json={"message": "hello"}
        )
        # Should return 503 (service unavailable) when agent not ready
        assert response.status_code == 503
        data = response.json()
        assert "error" in data["detail"] or "Agent not ready" in str(data)


class TestLegacyEndpoints:
    """Test legacy API endpoints for backward compatibility."""
    
    def test_legacy_status(self, client):
        """Test legacy /api/status endpoint."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "running"
        assert "version" in data
    
    def test_legacy_sessions(self, client):
        """Test legacy /api/sessions endpoint."""
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.json()
        
        assert "sessions" in data
    
    def test_legacy_channels(self, client):
        """Test legacy /api/channels endpoint."""
        response = client.get("/api/channels")
        assert response.status_code == 200
        data = response.json()
        
        assert "channels" in data


class TestConfigEndpoints:
    """Test /api/config/* endpoints."""
    
    def test_get_routing(self, client):
        """Test getting routing config."""
        response = client.get("/api/config/routing")
        assert response.status_code == 200
        data = response.json()
        
        assert "enabled" in data
        assert "fallback_tier" in data
    
    def test_get_memory(self, client):
        """Test getting memory config."""
        response = client.get("/api/config/memory")
        assert response.status_code == 200
        data = response.json()
        
        assert "enabled" in data
        assert "vector_search" in data
        assert "context_memories" in data
    
    def test_get_team(self, client):
        """Test getting team config."""
        response = client.get("/api/config/team")
        assert response.status_code == 200
        data = response.json()
        
        assert "team" in data
        assert "swarm" in data


class TestAgentStateTransitions:
    """Test agent state transitions."""
    
    def test_reinitialize_without_key(self, client):
        """Test reinitialize fails gracefully without API key."""
        response = client.post("/api/system/reinitialize")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == False
        assert data["agent_state"] == "uninitialized"
    
    def test_provider_update_triggers_reinit(self, client, mock_config):
        """Test that updating provider triggers reinitialize attempt."""
        # Update provider with key
        response = client.put(
            "/api/providers/openrouter",
            json={"api_key": "sk-test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have attempted reinitialize
        # (will fail without actual provider, but state should change)
        assert "agent_state" in data


class TestStaticFiles:
    """Test static file serving."""
    
    def test_root_returns_html(self, client):
        """Test root returns HTML (dashboard or fallback)."""
        response = client.get("/")
        assert response.status_code in [200, 503]  # 503 if no build
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_favicon(self, client):
        """Test favicon endpoint."""
        response = client.get("/favicon.svg")
        assert response.status_code == 200
        assert "svg" in response.headers.get("content-type", "")
