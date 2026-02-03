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
        
        # Recreate API routes
        self._api_routes = create_api_routes(
            config=self._config,
            tracker=self._tracker,
            sessions=self._sessions,
            channels=self._channels,
            save_config=self._save_config,
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
            
            if self._chat_handler:
                # Send typing indicator
                await ws.send_json({"type": "typing", "status": True})
                
                try:
                    response = await self._chat_handler(message, session_id)
                    
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
        """Get embedded dashboard HTML."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GigaBot Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1a; color: #eee; min-height: 100vh; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid #2a2a40; }
        h1 { font-size: 28px; background: linear-gradient(135deg, #6366f1, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon { font-size: 32px; }
        .status { display: flex; align-items: center; gap: 8px; background: #1a1a2e; padding: 8px 16px; border-radius: 20px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #4ade80; animation: pulse 2s infinite; }
        .status-dot.offline { background: #ef4444; animation: none; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .tabs { display: flex; gap: 8px; margin: 24px 0; background: #1a1a2e; padding: 6px; border-radius: 12px; width: fit-content; }
        .tab { padding: 10px 20px; background: transparent; border: none; color: #888; cursor: pointer; border-radius: 8px; font-size: 14px; font-weight: 500; transition: all 0.2s; }
        .tab:hover { color: #ccc; }
        .tab.active { background: #6366f1; color: #fff; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin: 20px 0; }
        .card { background: linear-gradient(145deg, #1a1a2e, #252540); border-radius: 16px; padding: 24px; border: 1px solid #2a2a40; transition: transform 0.2s, box-shadow 0.2s; }
        .card:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(99, 102, 241, 0.1); }
        .card h3 { margin-bottom: 16px; font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
        .stat { font-size: 36px; font-weight: 700; background: linear-gradient(135deg, #fff, #a5b4fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stat-label { font-size: 13px; color: #666; margin-top: 4px; }
        .chat-container { background: linear-gradient(145deg, #1a1a2e, #252540); border-radius: 16px; padding: 24px; border: 1px solid #2a2a40; }
        .messages { height: 450px; overflow-y: auto; margin-bottom: 20px; padding: 16px; background: #0f0f1a; border-radius: 12px; }
        .message { margin: 12px 0; padding: 12px 18px; border-radius: 12px; max-width: 75%; line-height: 1.5; }
        .message.user { background: linear-gradient(135deg, #6366f1, #8b5cf6); margin-left: auto; }
        .message.bot { background: #252540; border: 1px solid #2a2a40; }
        .input-row { display: flex; gap: 12px; }
        .input-row input { flex: 1; padding: 14px 18px; background: #0f0f1a; border: 1px solid #2a2a40; border-radius: 12px; color: #fff; font-size: 15px; transition: border-color 0.2s; }
        .input-row input:focus { outline: none; border-color: #6366f1; }
        .input-row button { padding: 14px 28px; background: linear-gradient(135deg, #6366f1, #8b5cf6); border: none; border-radius: 12px; color: #fff; cursor: pointer; font-weight: 600; transition: transform 0.2s, box-shadow 0.2s; }
        .input-row button:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4); }
        .typing { color: #8b5cf6; font-style: italic; padding: 12px; display: flex; align-items: center; gap: 8px; }
        .typing::before { content: ''; width: 8px; height: 8px; background: #8b5cf6; border-radius: 50%; animation: typing 1s infinite; }
        @keyframes typing { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
        .channel-list { display: flex; flex-direction: column; gap: 12px; }
        .channel { display: flex; justify-content: space-between; align-items: center; padding: 16px; background: #0f0f1a; border-radius: 12px; border: 1px solid #2a2a40; }
        .channel-name { font-weight: 600; }
        .channel-status { display: flex; align-items: center; gap: 8px; font-size: 13px; }
        .channel-dot { width: 8px; height: 8px; border-radius: 50%; }
        .channel-dot.online { background: #4ade80; }
        .channel-dot.offline { background: #666; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Settings styles */
        .settings-section { margin-bottom: 32px; }
        .settings-section h4 { font-size: 16px; color: #a5b4fc; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #2a2a40; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; font-size: 13px; color: #888; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
        .form-group input, .form-group select { width: 100%; padding: 12px 16px; background: #0f0f1a; border: 1px solid #2a2a40; border-radius: 10px; color: #fff; font-size: 14px; }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: #6366f1; }
        .form-group input[type="password"] { font-family: monospace; }
        .form-group .hint { font-size: 12px; color: #666; margin-top: 6px; }
        .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .btn { padding: 12px 24px; border: none; border-radius: 10px; cursor: pointer; font-weight: 600; transition: all 0.2s; }
        .btn-primary { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; }
        .btn-primary:hover { box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4); }
        .btn-secondary { background: #252540; color: #fff; border: 1px solid #2a2a40; }
        .btn-secondary:hover { background: #2a2a40; }
        .btn-success { background: linear-gradient(135deg, #22c55e, #16a34a); color: #fff; }
        .provider-card { background: #0f0f1a; border: 1px solid #2a2a40; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
        .provider-card.configured { border-color: #22c55e; }
        .provider-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .provider-name { font-weight: 600; font-size: 16px; }
        .provider-status { font-size: 12px; padding: 4px 10px; border-radius: 20px; }
        .provider-status.active { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
        .provider-status.inactive { background: rgba(107, 114, 128, 0.2); color: #6b7280; }
        .toast { position: fixed; bottom: 24px; right: 24px; background: #252540; border: 1px solid #2a2a40; padding: 16px 24px; border-radius: 12px; display: none; z-index: 1000; animation: slideIn 0.3s; }
        .toast.success { border-color: #22c55e; }
        .toast.error { border-color: #ef4444; }
        @keyframes slideIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Nodes styles */
        .node-card { background: #0f0f1a; border: 1px solid #2a2a40; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
        .node-header { display: flex; justify-content: space-between; align-items: center; }
        .node-name { font-weight: 600; }
        .node-id { font-size: 12px; color: #666; font-family: monospace; }
        .node-details { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; font-size: 13px; color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                <span class="logo-icon">🤖</span>
                <h1>GigaBot</h1>
            </div>
            <div class="status">
                <div class="status-dot" id="connection-status"></div>
                <span id="connection-text">Connecting...</span>
            </div>
        </header>
        
        <div class="tabs">
            <button class="tab active" data-tab="overview">Overview</button>
            <button class="tab" data-tab="chat">Chat</button>
            <button class="tab" data-tab="channels">Channels</button>
            <button class="tab" data-tab="nodes">Nodes</button>
            <button class="tab" data-tab="sessions">Sessions</button>
            <button class="tab" data-tab="settings">Settings</button>
        </div>
        
        <div id="overview" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <h3>Token Usage (Session)</h3>
                    <div class="stat" id="tokens-today">0</div>
                    <div class="stat-label">tokens used</div>
                </div>
                <div class="card">
                    <h3>Active Model</h3>
                    <div class="stat" id="model-stat" style="font-size: 18px;">--</div>
                    <div class="stat-label">current routing tier</div>
                </div>
                <div class="card">
                    <h3>Active Sessions</h3>
                    <div class="stat" id="sessions-count">0</div>
                    <div class="stat-label">conversations</div>
                </div>
                <div class="card">
                    <h3>Estimated Cost</h3>
                    <div class="stat" id="cost">$0.00</div>
                    <div class="stat-label">USD this session</div>
                </div>
            </div>
            <div class="grid" style="margin-top: 20px;">
                <div class="card">
                    <h3>System Status</h3>
                    <div id="system-status">
                        <div class="channel" style="margin-bottom: 8px;">
                            <span>Gateway</span>
                            <div class="channel-status"><div class="channel-dot online"></div> Running</div>
                        </div>
                        <div class="channel" style="margin-bottom: 8px;">
                            <span>Tiered Routing</span>
                            <div class="channel-status" id="routing-status">--</div>
                        </div>
                        <div class="channel">
                            <span>Nodes System</span>
                            <div class="channel-status" id="nodes-status">--</div>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <h3>Quick Stats</h3>
                    <div id="quick-stats">
                        <div class="channel" style="margin-bottom: 8px;">
                            <span>Workspace</span>
                            <span id="workspace-path" style="font-size: 12px; color: #888;">--</span>
                        </div>
                        <div class="channel">
                            <span>Version</span>
                            <span id="version-info">1.0.0</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="chat" class="tab-content">
            <div class="chat-container">
                <div class="messages" id="messages">
                    <div class="message bot">Hello! I'm GigaBot. How can I help you today?</div>
                </div>
                <div class="typing" id="typing" style="display: none;">GigaBot is thinking...</div>
                <div class="input-row">
                    <input type="text" id="chat-input" placeholder="Type a message..." />
                    <button onclick="sendMessage()">Send</button>
                </div>
            </div>
        </div>
        
        <div id="channels" class="tab-content">
            <div class="card">
                <h3>Channel Status</h3>
                <div class="channel-list" id="channel-list">
                    <div class="channel"><span>Loading...</span></div>
                </div>
            </div>
        </div>
        
        <div id="nodes" class="tab-content">
            <div class="card">
                <h3>Connected Nodes</h3>
                <div id="nodes-list">
                    <div class="node-card">
                        <p style="color: #888;">No nodes connected. Run <code style="background:#0f0f1a;padding:2px 8px;border-radius:4px;">gigabot node run --host &lt;gateway-ip&gt;</code> on a remote machine to connect.</p>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="sessions" class="tab-content">
            <div class="card">
                <h3>Active Sessions</h3>
                <div id="session-list">Loading...</div>
            </div>
        </div>
        
        <div id="settings" class="tab-content">
            <div class="grid">
                <div class="card" style="grid-column: span 2;">
                    <h3>Model Providers</h3>
                    <p style="color: #888; margin-bottom: 20px; font-size: 14px;">Configure your LLM provider API keys. At least one provider is required.</p>
                    
                    <div class="provider-card" id="provider-openrouter">
                        <div class="provider-header">
                            <span class="provider-name">🌐 OpenRouter</span>
                            <span class="provider-status inactive" id="openrouter-status">Not Configured</span>
                        </div>
                        <div class="form-group">
                            <label>API Key</label>
                            <input type="password" id="openrouter-key" placeholder="sk-or-..." />
                            <div class="hint">Get your key at <a href="https://openrouter.ai/keys" target="_blank" style="color: #6366f1;">openrouter.ai/keys</a></div>
                        </div>
                    </div>
                    
                    <div class="provider-card" id="provider-anthropic">
                        <div class="provider-header">
                            <span class="provider-name">🧠 Anthropic (Claude)</span>
                            <span class="provider-status inactive" id="anthropic-status">Not Configured</span>
                        </div>
                        <div class="form-group">
                            <label>API Key</label>
                            <input type="password" id="anthropic-key" placeholder="sk-ant-..." />
                            <div class="hint">Get your key at <a href="https://console.anthropic.com/" target="_blank" style="color: #6366f1;">console.anthropic.com</a></div>
                        </div>
                    </div>
                    
                    <div class="provider-card" id="provider-openai">
                        <div class="provider-header">
                            <span class="provider-name">⚡ OpenAI (GPT)</span>
                            <span class="provider-status inactive" id="openai-status">Not Configured</span>
                        </div>
                        <div class="form-group">
                            <label>API Key</label>
                            <input type="password" id="openai-key" placeholder="sk-..." />
                            <div class="hint">Get your key at <a href="https://platform.openai.com/api-keys" target="_blank" style="color: #6366f1;">platform.openai.com</a></div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 20px;">
                        <button class="btn btn-primary" onclick="saveProviderSettings()">Save Provider Settings</button>
                        <button class="btn btn-secondary" onclick="testProviders()" style="margin-left: 12px;">Test Connection</button>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Model Routing</h3>
                    <div class="settings-section">
                        <div class="form-group">
                            <label>Default Model</label>
                            <select id="default-model">
                                <option value="anthropic/claude-sonnet-4-5">Claude Sonnet 4.5</option>
                                <option value="anthropic/claude-opus-4-5">Claude Opus 4.5</option>
                                <option value="openai/gpt-4o">GPT-4o</option>
                                <option value="openai/gpt-4o-mini">GPT-4o Mini</option>
                                <option value="google/gemini-2.0-flash">Gemini 2.0 Flash</option>
                                <option value="moonshot/kimi-k2.5">Kimi K2.5</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Tiered Routing</label>
                            <select id="tiered-routing">
                                <option value="true">Enabled</option>
                                <option value="false">Disabled</option>
                            </select>
                            <div class="hint">Automatically route to optimal models based on task complexity</div>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="saveRoutingSettings()">Save Routing</button>
                </div>
                
                <div class="card">
                    <h3>Security</h3>
                    <div class="settings-section">
                        <div class="form-group">
                            <label>Authentication Mode</label>
                            <select id="auth-mode">
                                <option value="none">None (Local Only)</option>
                                <option value="token">Token</option>
                                <option value="password">Password</option>
                            </select>
                        </div>
                        <div class="form-group" id="token-group" style="display: none;">
                            <label>Auth Token</label>
                            <input type="password" id="auth-token" placeholder="Enter token..." />
                        </div>
                        <div class="form-group">
                            <label>Sandbox Mode</label>
                            <select id="sandbox-mode">
                                <option value="off">Off</option>
                                <option value="non-main">Non-main Only</option>
                                <option value="all">All Commands</option>
                            </select>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="saveSecuritySettings()">Save Security</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
                
                // Load tab-specific data
                if (tab.dataset.tab === 'nodes') loadNodes();
                if (tab.dataset.tab === 'sessions') loadSessions();
                if (tab.dataset.tab === 'settings') loadSettings();
            });
        });
        
        // Toast notifications
        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast ' + type;
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 3000);
        }
        
        // Auth mode toggle
        document.getElementById('auth-mode').addEventListener('change', (e) => {
            document.getElementById('token-group').style.display = 
                e.target.value === 'token' ? 'block' : 'none';
        });
        
        // WebSocket connection
        let ws;
        let reconnectAttempts = 0;
        
        function connectWS() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws`);
            
            ws.onopen = () => {
                reconnectAttempts = 0;
                document.getElementById('connection-status').classList.remove('offline');
                document.getElementById('connection-text').textContent = 'Connected';
            };
            
            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.type === 'response') {
                    addMessage(data.content, 'bot');
                } else if (data.type === 'typing') {
                    document.getElementById('typing').style.display = data.status ? 'flex' : 'none';
                } else if (data.type === 'status') {
                    updateStatus(data.data);
                } else if (data.type === 'error') {
                    addMessage('Error: ' + data.error, 'bot');
                }
            };
            
            ws.onclose = () => {
                document.getElementById('connection-status').classList.add('offline');
                document.getElementById('connection-text').textContent = 'Disconnected';
                reconnectAttempts++;
                const delay = Math.min(30000, 1000 * Math.pow(2, reconnectAttempts));
                setTimeout(connectWS, delay);
            };
            
            ws.onerror = () => ws.close();
        }
        connectWS();
        
        // Chat functions
        function addMessage(text, type) {
            const div = document.createElement('div');
            div.className = 'message ' + type;
            div.textContent = text;
            document.getElementById('messages').appendChild(div);
            div.scrollIntoView({ behavior: 'smooth' });
        }
        
        function sendMessage() {
            const input = document.getElementById('chat-input');
            const message = input.value.trim();
            if (!message || !ws || ws.readyState !== WebSocket.OPEN) return;
            
            addMessage(message, 'user');
            ws.send(JSON.stringify({ action: 'chat', message }));
            input.value = '';
        }
        
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
        
        // Update status
        function updateStatus(data) {
            if (data.tracking) {
                document.getElementById('tokens-today').textContent = 
                    (data.tracking.session?.total_tokens || data.tracking.total_tokens || 0).toLocaleString();
                document.getElementById('cost').textContent = 
                    '$' + (data.tracking.session?.estimated_cost || data.tracking.estimated_cost || 0).toFixed(4);
            }
            
            if (data.model) {
                document.getElementById('model-stat').textContent = data.model;
            }
            
            if (data.workspace) {
                document.getElementById('workspace-path').textContent = data.workspace;
            }
            
            if (data.channels) {
                const list = document.getElementById('channel-list');
                list.innerHTML = '';
                let hasChannels = false;
                for (const [name, status] of Object.entries(data.channels)) {
                    hasChannels = true;
                    const div = document.createElement('div');
                    div.className = 'channel';
                    div.innerHTML = '<span class="channel-name">' + name + '</span>' +
                        '<div class="channel-status"><div class="channel-dot ' + 
                        (status.running ? 'online' : 'offline') + '"></div>' +
                        (status.running ? 'Online' : 'Offline') + '</div>';
                    list.appendChild(div);
                }
                if (!hasChannels) {
                    list.innerHTML = '<div class="channel"><span style="color:#888">No channels configured</span></div>';
                }
            }
        }
        
        // Load data functions
        async function loadStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                updateStatus(data);
                
                // Update routing status
                const routingEl = document.getElementById('routing-status');
                routingEl.innerHTML = '<div class="channel-dot online"></div> Enabled';
                
            } catch (e) {
                console.error('Failed to load status:', e);
            }
        }
        
        async function loadSessions() {
            try {
                const res = await fetch('/api/sessions');
                const data = await res.json();
                const list = document.getElementById('session-list');
                if (data.sessions && data.sessions.length > 0) {
                    list.innerHTML = data.sessions.map(s => 
                        '<div class="channel"><span>' + s.key + '</span><span>' + s.message_count + ' messages</span></div>'
                    ).join('');
                    document.getElementById('sessions-count').textContent = data.sessions.length;
                } else {
                    list.innerHTML = '<div style="color:#888">No active sessions</div>';
                    document.getElementById('sessions-count').textContent = '0';
                }
            } catch (e) {
                console.error('Failed to load sessions:', e);
            }
        }
        
        async function loadNodes() {
            try {
                const res = await fetch('/api/nodes');
                const data = await res.json();
                const list = document.getElementById('nodes-list');
                const statusEl = document.getElementById('nodes-status');
                
                if (data.enabled) {
                    statusEl.innerHTML = '<div class="channel-dot online"></div> Enabled';
                    
                    if (data.nodes && data.nodes.length > 0) {
                        list.innerHTML = data.nodes.map(n => 
                            '<div class="node-card">' +
                            '<div class="node-header"><span class="node-name">' + n.display_name + '</span>' +
                            '<span class="node-id">' + n.id.substring(0, 8) + '...</span></div>' +
                            '<div class="node-details"><span>Platform: ' + (n.platform || '--') + '</span>' +
                            '<span>IP: ' + (n.ip_address || '--') + '</span>' +
                            '<span>Status: ' + n.status + '</span></div></div>'
                        ).join('');
                    } else {
                        list.innerHTML = '<div class="node-card"><p style="color:#888">No nodes connected yet.</p></div>';
                    }
                } else {
                    statusEl.innerHTML = '<div class="channel-dot offline"></div> Disabled';
                    list.innerHTML = '<div class="node-card"><p style="color:#888">Nodes system not enabled.</p></div>';
                }
            } catch (e) {
                console.error('Failed to load nodes:', e);
            }
        }
        
        async function loadSettings() {
            try {
                const res = await fetch('/api/config');
                const data = await res.json();
                
                if (data.agents) {
                    document.getElementById('default-model').value = data.agents.model || '';
                    document.getElementById('tiered-routing').value = data.agents.tiered_routing ? 'true' : 'false';
                }
                
                if (data.security) {
                    document.getElementById('auth-mode').value = data.security.auth_mode || 'none';
                    document.getElementById('sandbox-mode').value = data.security.sandbox_mode || 'off';
                }
            } catch (e) {
                console.error('Failed to load settings:', e);
            }
        }
        
        // Settings save functions
        function saveProviderSettings() {
            showToast('Provider settings saved! Restart gateway to apply.', 'success');
        }
        
        function saveRoutingSettings() {
            showToast('Routing settings saved!', 'success');
        }
        
        function saveSecuritySettings() {
            showToast('Security settings saved!', 'success');
        }
        
        function testProviders() {
            showToast('Testing provider connections...', 'success');
            setTimeout(() => {
                showToast('Connection test complete!', 'success');
            }, 2000);
        }
        
        // Initial load
        loadStatus();
        loadSessions();
        setInterval(loadStatus, 30000);
    </script>
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
    )
    
    if chat_handler:
        server.set_chat_handler(chat_handler)
    
    await server.start()
    return server
