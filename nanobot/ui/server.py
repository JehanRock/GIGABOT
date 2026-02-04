"""
WebUI server for GigaBot dashboard.

Provides:
- HTTP API endpoints
- WebSocket for streaming
- WebSocket for nodes
- Static file serving
- Cookie-based authentication
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING
from datetime import datetime

from loguru import logger

from nanobot.ui.api import create_api_routes
from nanobot.ui.versions import get_version_manager
from nanobot.security.auth import DashboardAuth

if TYPE_CHECKING:
    from nanobot.nodes.manager import NodeManager
    from nanobot.cron.service import CronService

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None


class UIServer:
    """
    Web server for GigaBot dashboard.
    
    Features:
    - REST API for status, config, sessions
    - WebSocket for real-time chat streaming
    - Static file serving for dashboard UI
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 18790,
        static_dir: Path | None = None,
        auth_token: str = "",
        # Dependencies for API routes
        config: Any = None,
        tracker: Any = None,
        sessions: Any = None,
        channels: Any = None,
        node_manager: "NodeManager | None" = None,
        cron_service: "CronService | None" = None,
    ):
        if not AIOHTTP_AVAILABLE:
            raise ImportError(
                "aiohttp not installed. Install with: pip install aiohttp"
            )
        
        self.host = host
        self.port = port
        self.static_dir = static_dir
        self.auth_token = auth_token
        
        # Store dependencies
        self._config = config
        self._tracker = tracker
        self._sessions = sessions
        self._channels = channels
        self._node_manager = node_manager
        self._cron_service = cron_service
        
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        
        # Callbacks for backward compatibility
        self._chat_handler: Callable | None = None
        self._status_handler: Callable | None = None
        self._save_config_handler: Callable | None = None
        
        # Dashboard authentication
        self._dashboard_auth: DashboardAuth | None = None
        self._init_dashboard_auth()
        
        # Create API routes
        self._api_routes = create_api_routes(
            config=config,
            tracker=tracker,
            sessions=sessions,
            channels=channels,
            save_config=self._save_config,
            cron_service=cron_service,
        )
        
        # WebSocket connections
        self._ws_connections: set[web.WebSocketResponse] = set()
    
    def set_chat_handler(self, handler: Callable) -> None:
        """Set the chat message handler."""
        self._chat_handler = handler
    
    def set_status_handler(self, handler: Callable) -> None:
        """Set the status handler (for backward compatibility)."""
        self._status_handler = handler
    
    def set_save_config_handler(self, handler: Callable) -> None:
        """Set the config save handler."""
        self._save_config_handler = handler
    
    async def _save_config(self) -> None:
        """Save config using the handler if set."""
        if self._save_config_handler:
            try:
                result = self._save_config_handler()
                # Handle both sync and async handlers
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Failed to save config: {e}")
    
    def _init_dashboard_auth(self) -> None:
        """Initialize dashboard authentication from config."""
        if not self._config:
            self._dashboard_auth = DashboardAuth()
            return
        
        auth_config = self._config.security.auth
        self._dashboard_auth = DashboardAuth(
            password_hash=auth_config.password_hash,
            password_salt=auth_config.password_salt,
            pin_hash=auth_config.pin_hash,
            pin_salt=auth_config.pin_salt,
            require_pin=auth_config.require_pin,
            session_duration_days=auth_config.session_duration_days,
        )
    
    def set_dependencies(
        self,
        config: Any = None,
        tracker: Any = None,
        sessions: Any = None,
        channels: Any = None,
        node_manager: "NodeManager | None" = None,
        cron_service: "CronService | None" = None,
    ) -> None:
        """Update dependencies after initialization."""
        if config:
            self._config = config
        if tracker:
            self._tracker = tracker
        if sessions:
            self._sessions = sessions
        if channels:
            self._channels = channels
        if node_manager:
            self._node_manager = node_manager
        if cron_service:
            self._cron_service = cron_service
        
        # Recreate API routes
        self._api_routes = create_api_routes(
            config=self._config,
            tracker=self._tracker,
            sessions=self._sessions,
            channels=self._channels,
            save_config=self._save_config,
            cron_service=self._cron_service,
        )
    
    def set_node_manager(self, node_manager: "NodeManager") -> None:
        """Set the node manager for handling node connections."""
        self._node_manager = node_manager
    
    async def start(self) -> None:
        """Start the web server."""
        self._app = web.Application(middlewares=[self._auth_middleware])
        
        # Setup routes
        self._setup_routes()
        
        # Start server
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        
        logger.info(f"WebUI server started at http://{self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop the web server."""
        # Close all WebSocket connections
        for ws in self._ws_connections:
            await ws.close()
        self._ws_connections.clear()
        
        if self._runner:
            await self._runner.cleanup()
        
        logger.info("WebUI server stopped")
    
    def _setup_routes(self) -> None:
        """Setup HTTP routes."""
        # API routes
        self._app.router.add_get("/api/status", self._handle_status)
        self._app.router.add_get("/api/system/status", self._handle_system_status)
        self._app.router.add_get("/api/config", self._handle_config)
        self._app.router.add_post("/api/chat", self._handle_chat)
        self._app.router.add_get("/api/sessions", self._handle_sessions)
        self._app.router.add_get("/api/tracking", self._handle_tracking)
        self._app.router.add_get("/api/channels", self._handle_channels)
        self._app.router.add_get("/api/memory", self._handle_memory)
        self._app.router.add_get("/api/nodes", self._handle_nodes)
        self._app.router.add_get("/health", self._handle_health)
        
        # Dashboard version management API
        self._app.router.add_get("/api/dashboard/versions", self._handle_dashboard_versions)
        self._app.router.add_post("/api/dashboard/deploy", self._handle_dashboard_deploy)
        self._app.router.add_post("/api/dashboard/rollback", self._handle_dashboard_rollback)
        
        # Gateway management API
        self._app.router.add_get("/api/gateways", self._handle_get_gateways)
        self._app.router.add_post("/api/gateways", self._handle_add_gateway)
        self._app.router.add_put("/api/gateways/{gateway_id}", self._handle_update_gateway)
        self._app.router.add_delete("/api/gateways/{gateway_id}", self._handle_delete_gateway)
        self._app.router.add_post("/api/gateways/{gateway_id}/test", self._handle_test_gateway)
        
        # Provider configuration API
        self._app.router.add_get("/api/providers", self._handle_get_providers)
        self._app.router.add_put("/api/providers/{provider}", self._handle_update_provider)
        
        # Routing configuration API
        self._app.router.add_get("/api/routing", self._handle_get_routing)
        self._app.router.add_put("/api/routing", self._handle_update_routing)
        
        # Memory configuration API
        self._app.router.add_get("/api/memory/config", self._handle_get_memory_config)
        self._app.router.add_put("/api/memory/config", self._handle_update_memory_config)
        
        # Team configuration API
        self._app.router.add_get("/api/team", self._handle_get_team_config)
        self._app.router.add_put("/api/team", self._handle_update_team_config)
        
        # Cron Jobs API
        self._app.router.add_get("/api/cron", self._handle_get_cron_jobs)
        self._app.router.add_post("/api/cron", self._handle_add_cron_job)
        self._app.router.add_post("/api/cron/{job_id}/run", self._handle_run_cron_job)
        self._app.router.add_put("/api/cron/{job_id}", self._handle_update_cron_job)
        self._app.router.add_delete("/api/cron/{job_id}", self._handle_delete_cron_job)
        
        # Authentication API
        self._app.router.add_get("/api/auth/status", self._handle_auth_status)
        self._app.router.add_post("/api/auth/login", self._handle_auth_login)
        self._app.router.add_post("/api/auth/verify-pin", self._handle_auth_verify_pin)
        self._app.router.add_post("/api/auth/logout", self._handle_auth_logout)
        self._app.router.add_post("/api/auth/setup", self._handle_auth_setup)
        
        # WebSocket - User chat
        self._app.router.add_get("/ws", self._handle_websocket)
        
        # WebSocket - Node connections
        self._app.router.add_get("/ws/nodes", self._handle_node_websocket)
        
        # Serve React dashboard static files from dist directory
        dist_dir = Path(__file__).parent / "dist"
        if dist_dir.exists():
            # Serve assets directory
            assets_dir = dist_dir / "assets"
            if assets_dir.exists():
                self._app.router.add_static("/assets", assets_dir)
            
            # Serve other static files
            self._app.router.add_get("/favicon.svg", self._handle_favicon)
            self._app.router.add_get("/favicon.ico", self._handle_favicon)
        
        # Legacy static files
        if self.static_dir and self.static_dir.exists():
            self._app.router.add_static("/static", self.static_dir)
        
        # Dashboard (SPA - serve index.html for all non-API routes)
        self._app.router.add_get("/", self._handle_dashboard)
        # Catch-all for SPA routing
        self._app.router.add_get("/{path:.*}", self._handle_spa_fallback)
    
    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler):
        """Authentication middleware."""
        # Skip auth for certain paths
        public_paths = ["/", "/health", "/favicon.ico", "/favicon.svg"]
        public_prefixes = ["/static", "/assets", "/api/auth/"]
        
        if request.path in public_paths:
            return await handler(request)
        
        for prefix in public_prefixes:
            if request.path.startswith(prefix):
                return await handler(request)
        
        # Check if dashboard auth is configured and required
        if self._dashboard_auth and self._dashboard_auth.is_configured:
            # Check session cookie
            session_id = request.cookies.get("gigabot_session")
            if session_id:
                valid, session = self._dashboard_auth.validate_session(session_id)
                if valid:
                    # Session valid, continue
                    request["session"] = session
                    return await handler(request)
            
            # No valid session, check for token fallback
            if self.auth_token:
                auth_header = request.headers.get("Authorization", "")
                token = auth_header.replace("Bearer ", "")
                if token == self.auth_token:
                    return await handler(request)
            
            # If accessing API, return 401 for AJAX handling
            if request.path.startswith("/api/"):
                return web.json_response(
                    {"error": "Unauthorized", "auth_required": True},
                    status=401
                )
            
            # For page requests, serve the login page (SPA will handle)
            return await handler(request)
        
        # Legacy token-only auth
        if self.auth_token:
            auth_header = request.headers.get("Authorization", "")
            token = auth_header.replace("Bearer ", "")
            
            if token != self.auth_token:
                return web.json_response(
                    {"error": "Unauthorized"},
                    status=401
                )
        
        return await handler(request)
    
    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "ok"})
    
    async def _handle_status(self, request: web.Request) -> web.Response:
        """Handle status request."""
        # Use API route
        status = await self._api_routes["status"]()
        
        # Add legacy status handler if set
        if self._status_handler:
            try:
                extra = await self._status_handler()
                status.update(extra)
            except Exception as e:
                logger.warning(f"Status handler error: {e}")
        
        return web.json_response(status)
    
    async def _handle_system_status(self, request: web.Request) -> web.Response:
        """
        Handle system status request for frontend.
        
        Returns comprehensive system state for the dashboard.
        """
        config = self._config
        
        # Determine agent state based on chat handler presence
        has_chat_handler = self._chat_handler is not None
        has_api_key = self._has_any_api_key()
        
        if has_api_key and has_chat_handler:
            agent_state = "ready"
            is_ready = True
        elif has_api_key and not has_chat_handler:
            agent_state = "initializing"
            is_ready = False
        else:
            agent_state = "uninitialized"
            is_ready = False
        
        # Get configured providers
        configured_providers = []
        primary_provider = None
        
        if config:
            providers = config.providers
            if providers.openrouter.api_key:
                configured_providers.append("openrouter")
                if not primary_provider:
                    primary_provider = "openrouter"
            if providers.anthropic.api_key:
                configured_providers.append("anthropic")
                if not primary_provider:
                    primary_provider = "anthropic"
            if providers.openai.api_key:
                configured_providers.append("openai")
                if not primary_provider:
                    primary_provider = "openai"
            if providers.moonshot.api_key:
                configured_providers.append("moonshot")
            if providers.deepseek.api_key:
                configured_providers.append("deepseek")
        
        return web.json_response({
            "agent_state": agent_state,
            "is_ready": is_ready,
            "has_api_key": has_api_key,
            "configured_providers": configured_providers,
            "primary_provider": primary_provider,
            "version": "0.1.0",
            "error": None,
            "model": config.agents.defaults.model if config else None,
            "workspace": str(config.workspace_path) if config else None,
            "tiered_routing_enabled": config.agents.tiered_routing.enabled if config else False,
            "memory_enabled": config.agents.memory.enabled if config else False,
        })
    
    def _has_any_api_key(self) -> bool:
        """Check if any API key is configured."""
        import os
        
        if self._config:
            providers = self._config.providers
            if providers.openrouter.api_key:
                return True
            if providers.anthropic.api_key:
                return True
            if providers.openai.api_key:
                return True
            if providers.moonshot.api_key:
                return True
            if providers.deepseek.api_key:
                return True
        
        # Check environment
        env_vars = ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
        for var in env_vars:
            if os.environ.get(var, "").strip():
                return True
        
        return False
    
    async def _handle_config(self, request: web.Request) -> web.Response:
        """Handle config request."""
        config = await self._api_routes["config"]()
        return web.json_response(config)
    
    async def _handle_sessions(self, request: web.Request) -> web.Response:
        """Handle sessions list request."""
        sessions = await self._api_routes["sessions"]()
        return web.json_response(sessions)
    
    async def _handle_tracking(self, request: web.Request) -> web.Response:
        """Handle tracking stats request."""
        tracking = await self._api_routes["tracking"]()
        return web.json_response(tracking)
    
    async def _handle_channels(self, request: web.Request) -> web.Response:
        """Handle channels status request."""
        channels = await self._api_routes["channels"]()
        return web.json_response(channels)
    
    async def _handle_memory(self, request: web.Request) -> web.Response:
        """Handle memory stats request."""
        memory = await self._api_routes["memory"]()
        return web.json_response(memory)
    
    # Gateway management handlers
    async def _handle_get_gateways(self, request: web.Request) -> web.Response:
        """Handle get gateways request."""
        gateways = await self._api_routes["gateways"]()
        return web.json_response(gateways)
    
    async def _handle_add_gateway(self, request: web.Request) -> web.Response:
        """Handle add gateway request."""
        try:
            data = await request.json()
            result = await self._api_routes["add_gateway"](data)
            
            if "error" in result:
                return web.json_response(result, status=400)
            
            return web.json_response(result, status=201)
        except Exception as e:
            logger.error(f"Add gateway error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_update_gateway(self, request: web.Request) -> web.Response:
        """Handle update gateway request."""
        try:
            gateway_id = request.match_info.get("gateway_id")
            data = await request.json()
            result = await self._api_routes["update_gateway"](gateway_id, data)
            
            if "error" in result:
                return web.json_response(result, status=404 if "not found" in result["error"].lower() else 400)
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Update gateway error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_delete_gateway(self, request: web.Request) -> web.Response:
        """Handle delete gateway request."""
        try:
            gateway_id = request.match_info.get("gateway_id")
            result = await self._api_routes["delete_gateway"](gateway_id)
            
            if "error" in result:
                return web.json_response(result, status=404)
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Delete gateway error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_test_gateway(self, request: web.Request) -> web.Response:
        """Handle test gateway request."""
        try:
            gateway_id = request.match_info.get("gateway_id")
            result = await self._api_routes["test_gateway"](gateway_id)
            
            if "error" in result and "not found" in result.get("error", "").lower():
                return web.json_response(result, status=404)
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Test gateway error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Provider configuration handlers
    async def _handle_get_providers(self, request: web.Request) -> web.Response:
        """Handle get providers request."""
        try:
            result = await self._api_routes["providers"]()
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Get providers error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_update_provider(self, request: web.Request) -> web.Response:
        """Handle update provider request."""
        try:
            provider = request.match_info.get("provider")
            data = await request.json()
            result = await self._api_routes["update_provider"](provider, data)
            
            if "error" in result:
                status = 404 if "Unknown" in result.get("error", "") else 400
                return web.json_response(result, status=status)
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Update provider error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Routing configuration handlers
    async def _handle_get_routing(self, request: web.Request) -> web.Response:
        """Handle get routing request."""
        try:
            result = await self._api_routes["routing"]()
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Get routing error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_update_routing(self, request: web.Request) -> web.Response:
        """Handle update routing request."""
        try:
            data = await request.json()
            result = await self._api_routes["update_routing"](data)
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Update routing error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Memory configuration handlers
    async def _handle_get_memory_config(self, request: web.Request) -> web.Response:
        """Handle get memory config request."""
        try:
            result = await self._api_routes["memory_config"]()
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Get memory config error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_update_memory_config(self, request: web.Request) -> web.Response:
        """Handle update memory config request."""
        try:
            data = await request.json()
            result = await self._api_routes["update_memory_config"](data)
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Update memory config error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Team configuration handlers
    async def _handle_get_team_config(self, request: web.Request) -> web.Response:
        """Handle get team config request."""
        try:
            result = await self._api_routes["team_config"]()
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Get team config error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_update_team_config(self, request: web.Request) -> web.Response:
        """Handle update team config request."""
        try:
            data = await request.json()
            result = await self._api_routes["update_team_config"](data)
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Update team config error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Cron Jobs handlers
    async def _handle_get_cron_jobs(self, request: web.Request) -> web.Response:
        """Handle get cron jobs request."""
        try:
            result = await self._api_routes["cron_jobs"]()
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Get cron jobs error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_add_cron_job(self, request: web.Request) -> web.Response:
        """Handle add cron job request."""
        try:
            data = await request.json()
            result = await self._api_routes["add_cron_job"](data)
            
            if "error" in result:
                return web.json_response(result, status=400)
            
            return web.json_response(result, status=201)
        except Exception as e:
            logger.error(f"Add cron job error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_run_cron_job(self, request: web.Request) -> web.Response:
        """Handle run cron job request."""
        try:
            job_id = request.match_info.get("job_id")
            data = {}
            try:
                data = await request.json()
            except Exception:
                pass  # Optional body
            
            force = data.get("force", False)
            result = await self._api_routes["run_cron_job"](job_id, force)
            
            if "error" in result:
                status = 404 if "not found" in result.get("error", "").lower() else 400
                return web.json_response(result, status=status)
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Run cron job error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_update_cron_job(self, request: web.Request) -> web.Response:
        """Handle update cron job request."""
        try:
            job_id = request.match_info.get("job_id")
            data = await request.json()
            result = await self._api_routes["update_cron_job"](job_id, data)
            
            if "error" in result:
                status = 404 if "not found" in result.get("error", "").lower() else 400
                return web.json_response(result, status=status)
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Update cron job error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_delete_cron_job(self, request: web.Request) -> web.Response:
        """Handle delete cron job request."""
        try:
            job_id = request.match_info.get("job_id")
            result = await self._api_routes["delete_cron_job"](job_id)
            
            if "error" in result:
                return web.json_response(result, status=404)
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Delete cron job error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    # Authentication handlers
    async def _handle_auth_status(self, request: web.Request) -> web.Response:
        """Get authentication status."""
        if not self._dashboard_auth:
            return web.json_response({
                "configured": False,
                "authenticated": False,
            })
        
        # Check if user has valid session
        session_id = request.cookies.get("gigabot_session")
        authenticated = False
        session_info = None
        
        if session_id:
            valid, session = self._dashboard_auth.validate_session(session_id)
            authenticated = valid
            if session:
                session_info = session.to_dict()
        
        status = self._dashboard_auth.get_auth_status()
        status["authenticated"] = authenticated
        status["session"] = session_info
        
        return web.json_response(status)
    
    async def _handle_auth_login(self, request: web.Request) -> web.Response:
        """Handle password login."""
        if not self._dashboard_auth:
            return web.json_response({"error": "Auth not configured"}, status=500)
        
        try:
            data = await request.json()
            password = data.get("password", "")
            
            if not password:
                return web.json_response({"error": "Password required"}, status=400)
            
            # Get client info
            ip_address = request.remote or ""
            user_agent = request.headers.get("User-Agent", "")
            
            success, token_or_session, message = self._dashboard_auth.login(
                password, ip_address, user_agent
            )
            
            if not success:
                return web.json_response({"error": message}, status=401)
            
            # Check if PIN is required
            if message == "PIN required":
                return web.json_response({
                    "success": True,
                    "require_pin": True,
                    "temp_token": token_or_session,
                    "message": message,
                })
            
            # No PIN required, session created directly
            response = web.json_response({
                "success": True,
                "require_pin": False,
                "message": message,
            })
            
            # Set session cookie
            self._set_session_cookie(response, token_or_session)
            
            return response
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_auth_verify_pin(self, request: web.Request) -> web.Response:
        """Handle PIN verification."""
        if not self._dashboard_auth:
            return web.json_response({"error": "Auth not configured"}, status=500)
        
        try:
            data = await request.json()
            temp_token = data.get("temp_token", "")
            pin = data.get("pin", "")
            
            if not temp_token or not pin:
                return web.json_response({"error": "Token and PIN required"}, status=400)
            
            # Get client info
            ip_address = request.remote or ""
            user_agent = request.headers.get("User-Agent", "")
            
            success, session_id, message = self._dashboard_auth.verify_pin(
                temp_token, pin, ip_address, user_agent
            )
            
            if not success:
                return web.json_response({"error": message}, status=401)
            
            response = web.json_response({
                "success": True,
                "message": message,
            })
            
            # Set session cookie
            self._set_session_cookie(response, session_id)
            
            return response
            
        except Exception as e:
            logger.error(f"PIN verification error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_auth_logout(self, request: web.Request) -> web.Response:
        """Handle logout."""
        session_id = request.cookies.get("gigabot_session")
        
        if session_id and self._dashboard_auth:
            self._dashboard_auth.logout(session_id)
        
        response = web.json_response({"success": True, "message": "Logged out"})
        
        # Clear session cookie
        response.del_cookie("gigabot_session", path="/")
        
        return response
    
    async def _handle_auth_setup(self, request: web.Request) -> web.Response:
        """Handle initial auth setup (password and PIN)."""
        if not self._dashboard_auth:
            self._dashboard_auth = DashboardAuth()
        
        # Only allow setup if not already configured
        if self._dashboard_auth.is_configured:
            return web.json_response(
                {"error": "Authentication already configured"},
                status=400
            )
        
        try:
            data = await request.json()
            password = data.get("password", "")
            pin = data.get("pin", "")
            
            if not password:
                return web.json_response({"error": "Password required"}, status=400)
            
            if len(password) < 8:
                return web.json_response(
                    {"error": "Password must be at least 8 characters"},
                    status=400
                )
            
            # Setup password
            password_hash, password_salt = self._dashboard_auth.setup_password(password)
            
            # Setup PIN if provided
            pin_hash, pin_salt = "", ""
            if pin:
                if not pin.isdigit() or not (4 <= len(pin) <= 8):
                    return web.json_response(
                        {"error": "PIN must be 4-8 digits"},
                        status=400
                    )
                pin_hash, pin_salt = self._dashboard_auth.setup_pin(pin)
            
            # Update config
            if self._config:
                self._config.security.auth.password_hash = password_hash
                self._config.security.auth.password_salt = password_salt
                self._config.security.auth.pin_hash = pin_hash
                self._config.security.auth.pin_salt = pin_salt
                self._config.security.auth.setup_complete = True
                self._config.security.auth.mode = "password"
                
                # Save config
                if self._save_config_handler:
                    await self._save_config()
            
            # Auto-login after setup
            ip_address = request.remote or ""
            user_agent = request.headers.get("User-Agent", "")
            
            # Create session directly (skip PIN for initial setup)
            session_id = self._dashboard_auth._create_session(ip_address, user_agent)
            
            response = web.json_response({
                "success": True,
                "message": "Authentication configured",
            })
            
            self._set_session_cookie(response, session_id)
            
            return response
            
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        except Exception as e:
            logger.error(f"Auth setup error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    def _set_session_cookie(self, response: web.Response, session_id: str) -> None:
        """Set the session cookie on response."""
        # Cookie settings for security
        max_age = 7 * 24 * 60 * 60  # 7 days in seconds
        
        response.set_cookie(
            "gigabot_session",
            session_id,
            max_age=max_age,
            httponly=True,  # Prevent XSS access
            secure=False,  # Set True for HTTPS only (handled by reverse proxy)
            samesite="Strict",  # CSRF protection
            path="/",
        )
    
    async def _handle_nodes(self, request: web.Request) -> web.Response:
        """Handle nodes list request."""
        if not self._node_manager:
            return web.json_response({
                "nodes": [],
                "enabled": False,
            })
        
        nodes = self._node_manager.list_nodes()
        pending = self._node_manager.list_pending()
        
        return web.json_response({
            "nodes": [n.to_dict() for n in nodes],
            "pending": [n.to_dict() for n in pending],
            "enabled": True,
            "connected_count": sum(1 for n in nodes if self._node_manager.is_connected(n.id)),
        })
    
    async def _handle_chat(self, request: web.Request) -> web.Response:
        """Handle chat message."""
        try:
            data = await request.json()
            message = data.get("message", "")
            session_id = data.get("session_id", "webui:default")
            
            if not message:
                return web.json_response(
                    {"error": "Message required"},
                    status=400
                )
            
            if self._chat_handler:
                response = await self._chat_handler(message, session_id)
                return web.json_response({"response": response})
            
            return web.json_response({"error": "Chat handler not configured"}, status=500)
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for streaming."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self._ws_connections.add(ws)
        logger.info("WebSocket client connected")
        
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_ws_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_json({"error": "Invalid JSON"})
                        
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    
        finally:
            self._ws_connections.discard(ws)
            logger.info("WebSocket client disconnected")
        
        return ws
    
    async def _handle_ws_message(self, ws: web.WebSocketResponse, data: dict) -> None:
        """Handle incoming WebSocket message."""
        action = data.get("action", "")
        
        if action == "chat":
            message = data.get("message", "")
            session_id = data.get("session_id", "webui:ws")
            model = data.get("model")  # Optional model override
            thinking_level = data.get("thinking_level", "medium")  # low/medium/high
            
            if self._chat_handler:
                # Send typing indicator
                await ws.send_json({"type": "typing", "status": True})
                
                try:
                    # Pass model and thinking_level as kwargs
                    response = await self._chat_handler(
                        message, 
                        session_id,
                        model=model,
                        thinking_level=thinking_level
                    )
                    
                    await ws.send_json({
                        "type": "response",
                        "content": response,
                        "session_id": session_id,
                    })
                except Exception as e:
                    await ws.send_json({
                        "type": "error",
                        "error": str(e),
                    })
                finally:
                    await ws.send_json({"type": "typing", "status": False})
            else:
                await ws.send_json({"error": "Chat handler not configured"})
        
        elif action == "ping":
            await ws.send_json({"type": "pong"})
        
        elif action == "status":
            status = await self._api_routes["status"]()
            await ws.send_json({"type": "status", "data": status})
        
        else:
            await ws.send_json({"error": f"Unknown action: {action}"})
    
    async def _handle_node_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection from a node host."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        if not self._node_manager:
            await ws.send_json({
                "type": "connect_reject",
                "payload": {"reason": "Nodes not enabled on this gateway"},
            })
            await ws.close()
            return ws
        
        # Get client IP address
        peername = request.transport.get_extra_info("peername")
        ip_address = peername[0] if peername else ""
        
        logger.info(f"Node WebSocket connection from {ip_address}")
        
        try:
            await self._node_manager.handle_connection(ws, ip_address)
        except Exception as e:
            logger.error(f"Node connection error: {e}")
        
        return ws
    
    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all WebSocket clients."""
        for ws in list(self._ws_connections):
            try:
                await ws.send_json(message)
            except Exception:
                self._ws_connections.discard(ws)
    
    async def _handle_dashboard_versions(self, request: web.Request) -> web.Response:
        """List available dashboard versions."""
        version_manager = get_version_manager()
        versions = version_manager.list_versions()
        current = version_manager.get_current_version()
        
        return web.json_response({
            "current_version": current,
            "versions": versions,
        })
    
    async def _handle_dashboard_deploy(self, request: web.Request) -> web.Response:
        """Deploy the staged dashboard build."""
        try:
            data = await request.json()
            version = data.get("version")
        except Exception:
            version = None
        
        version_manager = get_version_manager()
        result = await version_manager.deploy_staging(version)
        
        if result.get("status") == "error":
            return web.json_response(result, status=400)
        
        # Broadcast refresh event to connected clients
        await self.broadcast({
            "type": "dashboard:refresh",
            "version": result.get("version"),
        })
        
        return web.json_response(result)
    
    async def _handle_dashboard_rollback(self, request: web.Request) -> web.Response:
        """Rollback to a previous dashboard version."""
        try:
            data = await request.json()
            version = data.get("version")
            
            if not version:
                return web.json_response(
                    {"error": "Version is required"},
                    status=400
                )
        except Exception as e:
            return web.json_response(
                {"error": f"Invalid request: {e}"},
                status=400
            )
        
        version_manager = get_version_manager()
        result = await version_manager.rollback_to(version)
        
        if result.get("status") == "error":
            return web.json_response(result, status=400)
        
        # Broadcast refresh event to connected clients
        await self.broadcast({
            "type": "dashboard:refresh",
            "version": version,
        })
        
        return web.json_response(result)
    
    async def _handle_favicon(self, request: web.Request) -> web.Response:
        """Serve favicon from dist directory."""
        dist_dir = Path(__file__).parent / "dist"
        favicon_path = dist_dir / "favicon.svg"
        
        if favicon_path.exists():
            return web.FileResponse(favicon_path)
        
        # Fallback to generated favicon
        return web.Response(
            text='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="#6366f1" width="100" height="100" rx="20"/><text x="50" y="68" font-family="Arial" font-size="50" font-weight="bold" fill="white" text-anchor="middle">G</text></svg>',
            content_type="image/svg+xml"
        )
    
    async def _handle_spa_fallback(self, request: web.Request) -> web.Response:
        """Handle SPA routing - serve index.html for non-API routes."""
        path = request.match_info.get("path", "")
        
        # Don't intercept API, WebSocket, or static file requests
        if path.startswith(("api/", "ws", "assets/", "static/")):
            raise web.HTTPNotFound()
        
        # Try to serve as static file first
        dist_dir = Path(__file__).parent / "dist"
        file_path = dist_dir / path
        
        if file_path.exists() and file_path.is_file():
            return web.FileResponse(file_path)
        
        # Otherwise serve index.html (SPA routing)
        return await self._handle_dashboard(request)
    
    async def _handle_dashboard(self, request: web.Request) -> web.Response:
        """Serve the dashboard - React build if available, otherwise embedded HTML."""
        # Try to serve React dashboard from dist
        dist_dir = Path(__file__).parent / "dist"
        index_path = dist_dir / "index.html"
        
        if index_path.exists():
            return web.FileResponse(index_path)
        
        # Fallback to embedded dashboard
        html = self._get_dashboard_html()
        return web.Response(text=html, content_type="text/html")
    
    def _get_dashboard_html(self) -> str:
        """Get simple fallback HTML when React build is not available."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GigaBot Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: #0f0f1a; 
            color: #eee; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container { 
            text-align: center; 
            max-width: 500px; 
            padding: 40px;
        }
        h1 { 
            font-size: 32px; 
            background: linear-gradient(135deg, #6366f1, #8b5cf6); 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent;
            margin-bottom: 16px;
        }
        .icon { font-size: 64px; margin-bottom: 24px; }
        p { color: #888; margin-bottom: 24px; line-height: 1.6; }
        code { 
            display: block;
            background: #1a1a2e; 
            padding: 16px 24px; 
            border-radius: 12px; 
            margin: 16px 0;
            font-size: 14px;
            color: #a5b4fc;
            border: 1px solid #2a2a40;
        }
        .hint { 
            font-size: 13px; 
            color: #666; 
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid #2a2a40;
        }
        a { color: #6366f1; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🤖</div>
        <h1>GigaBot Dashboard</h1>
        <p>The React dashboard has not been built yet. To build it, run:</p>
        <code>cd nanobot/ui/dashboard && npm install && npm run build</code>
        <p>Or use the new FastAPI server with hot-reload:</p>
        <code>gigabot gateway-v2 --reload</code>
        <div class="hint">
            For development, you can run the frontend separately:<br>
            <code>cd nanobot/ui/dashboard && npm run dev</code>
            <br><br>
            <a href="/api/system/status">View API Status</a> | 
            <a href="/health">Health Check</a>
        </div>
    </div>
</body>
</html>"""


async def start_server(
    host: str = "127.0.0.1",
    port: int = 18790,
    auth_token: str = "",
    chat_handler: Callable | None = None,
    config: Any = None,
    tracker: Any = None,
    sessions: Any = None,
    channels: Any = None,
    node_manager: "NodeManager | None" = None,
    cron_service: "CronService | None" = None,
) -> UIServer:
    """
    Start the WebUI server.
    
    Args:
        host: Host to bind to.
        port: Port to listen on.
        auth_token: Optional authentication token.
        chat_handler: Handler for chat messages.
        config: Configuration object.
        tracker: TokenTracker instance.
        sessions: SessionManager instance.
        channels: ChannelManager instance.
        node_manager: NodeManager instance for node connections.
        cron_service: CronService instance for scheduled jobs.
    
    Returns:
        Running UIServer instance.
    """
    server = UIServer(
        host=host, 
        port=port, 
        auth_token=auth_token,
        config=config,
        tracker=tracker,
        sessions=sessions,
        channels=channels,
        node_manager=node_manager,
        cron_service=cron_service,
    )
    
    if chat_handler:
        server.set_chat_handler(chat_handler)
    
    await server.start()
    return server
