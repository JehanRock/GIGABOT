"""
WebUI server for GigaBot dashboard.

Provides:
- HTTP API endpoints
- WebSocket for streaming
- Static file serving
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from nanobot.ui.api import create_api_routes

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
        
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        
        # Callbacks for backward compatibility
        self._chat_handler: Callable | None = None
        self._status_handler: Callable | None = None
        
        # Create API routes
        self._api_routes = create_api_routes(
            config=config,
            tracker=tracker,
            sessions=sessions,
            channels=channels,
        )
        
        # WebSocket connections
        self._ws_connections: set[web.WebSocketResponse] = set()
    
    def set_chat_handler(self, handler: Callable) -> None:
        """Set the chat message handler."""
        self._chat_handler = handler
    
    def set_status_handler(self, handler: Callable) -> None:
        """Set the status handler (for backward compatibility)."""
        self._status_handler = handler
    
    def set_dependencies(
        self,
        config: Any = None,
        tracker: Any = None,
        sessions: Any = None,
        channels: Any = None,
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
        
        # Recreate API routes
        self._api_routes = create_api_routes(
            config=self._config,
            tracker=self._tracker,
            sessions=self._sessions,
            channels=self._channels,
        )
    
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
        self._app.router.add_get("/health", self._handle_health)
        
        # WebSocket
        self._app.router.add_get("/ws", self._handle_websocket)
        
        # Static files
        if self.static_dir and self.static_dir.exists():
            self._app.router.add_static("/static", self.static_dir)
        
        # Dashboard
        self._app.router.add_get("/", self._handle_dashboard)
    
    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler):
        """Authentication middleware."""
        # Skip auth for certain paths
        if request.path in ["/", "/health", "/favicon.ico"] or request.path.startswith("/static"):
            return await handler(request)
        
        # Check auth token
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
    
    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all WebSocket clients."""
        for ws in list(self._ws_connections):
            try:
                await ws.send_json(message)
            except Exception:
                self._ws_connections.discard(ws)
    
    async def _handle_dashboard(self, request: web.Request) -> web.Response:
        """Serve embedded dashboard HTML."""
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
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid #333; }
        h1 { font-size: 24px; }
        .status { display: flex; align-items: center; gap: 8px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #4ade80; }
        .status-dot.offline { background: #ef4444; }
        .tabs { display: flex; gap: 10px; margin: 20px 0; }
        .tab { padding: 10px 20px; background: #252540; border: none; color: #aaa; cursor: pointer; border-radius: 8px; }
        .tab.active { background: #3b3b5c; color: #fff; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }
        .card { background: #252540; border-radius: 12px; padding: 20px; }
        .card h3 { margin-bottom: 15px; font-size: 14px; color: #888; text-transform: uppercase; }
        .stat { font-size: 32px; font-weight: bold; }
        .stat-label { font-size: 12px; color: #666; }
        .chat-container { background: #252540; border-radius: 12px; padding: 20px; margin-top: 20px; }
        .messages { height: 400px; overflow-y: auto; margin-bottom: 20px; padding: 10px; }
        .message { margin: 10px 0; padding: 10px 15px; border-radius: 8px; max-width: 80%; }
        .message.user { background: #3b3b5c; margin-left: auto; }
        .message.bot { background: #1a1a2e; }
        .input-row { display: flex; gap: 10px; }
        .input-row input { flex: 1; padding: 12px 16px; background: #1a1a2e; border: 1px solid #333; border-radius: 8px; color: #fff; }
        .input-row button { padding: 12px 24px; background: #6366f1; border: none; border-radius: 8px; color: #fff; cursor: pointer; }
        .input-row button:hover { background: #5558dd; }
        .typing { color: #888; font-style: italic; padding: 10px; }
        .channel-list { display: flex; flex-direction: column; gap: 10px; }
        .channel { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #1a1a2e; border-radius: 8px; }
        .channel-name { font-weight: bold; }
        .channel-status { display: flex; align-items: center; gap: 5px; }
        .channel-dot { width: 8px; height: 8px; border-radius: 50%; }
        .channel-dot.online { background: #4ade80; }
        .channel-dot.offline { background: #666; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>GigaBot Dashboard</h1>
            <div class="status">
                <div class="status-dot" id="connection-status"></div>
                <span id="connection-text">Connecting...</span>
            </div>
        </header>
        
        <div class="tabs">
            <button class="tab active" data-tab="overview">Overview</button>
            <button class="tab" data-tab="chat">Chat</button>
            <button class="tab" data-tab="channels">Channels</button>
            <button class="tab" data-tab="sessions">Sessions</button>
        </div>
        
        <div id="overview" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <h3>Token Usage (Today)</h3>
                    <div class="stat" id="tokens-today">--</div>
                    <div class="stat-label">tokens</div>
                </div>
                <div class="card">
                    <h3>Efficiency Score</h3>
                    <div class="stat" id="efficiency">--</div>
                    <div class="stat-label">percent</div>
                </div>
                <div class="card">
                    <h3>Active Sessions</h3>
                    <div class="stat" id="sessions-count">--</div>
                    <div class="stat-label">sessions</div>
                </div>
                <div class="card">
                    <h3>Estimated Cost</h3>
                    <div class="stat" id="cost">$--</div>
                    <div class="stat-label">USD today</div>
                </div>
            </div>
            <div class="card" style="margin-top: 20px;">
                <h3>Model</h3>
                <div id="model-info">--</div>
            </div>
        </div>
        
        <div id="chat" class="tab-content">
            <div class="chat-container">
                <div class="messages" id="messages"></div>
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
                    <div class="channel">Loading...</div>
                </div>
            </div>
        </div>
        
        <div id="sessions" class="tab-content">
            <div class="card">
                <h3>Active Sessions</h3>
                <div id="session-list">Loading...</div>
            </div>
        </div>
    </div>
    
    <script>
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
            });
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
                    document.getElementById('typing').style.display = data.status ? 'block' : 'none';
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
            
            ws.onerror = () => {
                ws.close();
            };
        }
        connectWS();
        
        // Chat functions
        function addMessage(text, type) {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            div.textContent = text;
            document.getElementById('messages').appendChild(div);
            div.scrollIntoView({ behavior: 'smooth' });
        }
        
        function sendMessage() {
            const input = document.getElementById('chat-input');
            const message = input.value.trim();
            if (!message) return;
            
            addMessage(message, 'user');
            ws.send(JSON.stringify({ action: 'chat', message }));
            input.value = '';
        }
        
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
        
        // Update UI with status data
        function updateStatus(data) {
            if (data.tracking) {
                document.getElementById('tokens-today').textContent = 
                    (data.tracking.session?.total_tokens || 0).toLocaleString();
                document.getElementById('efficiency').textContent = 
                    data.tracking.efficiency_score || '--';
                document.getElementById('cost').textContent = 
                    '$' + (data.tracking.session?.estimated_cost || 0).toFixed(4);
            }
            
            if (data.model) {
                document.getElementById('model-info').textContent = data.model;
            }
            
            if (data.channels) {
                const list = document.getElementById('channel-list');
                list.innerHTML = '';
                for (const [name, status] of Object.entries(data.channels)) {
                    const div = document.createElement('div');
                    div.className = 'channel';
                    div.innerHTML = `
                        <span class="channel-name">${name}</span>
                        <div class="channel-status">
                            <div class="channel-dot ${status.running ? 'online' : 'offline'}"></div>
                            <span>${status.running ? 'Online' : 'Offline'}</span>
                        </div>
                    `;
                    list.appendChild(div);
                }
            }
        }
        
        // Load status periodically
        async function loadStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                updateStatus(data);
            } catch (e) {
                console.error('Failed to load status:', e);
            }
        }
        
        async function loadChannels() {
            try {
                const res = await fetch('/api/channels');
                const data = await res.json();
                if (data.channels) {
                    updateStatus({ channels: data.channels });
                }
            } catch (e) {
                console.error('Failed to load channels:', e);
            }
        }
        
        async function loadSessions() {
            try {
                const res = await fetch('/api/sessions');
                const data = await res.json();
                const list = document.getElementById('session-list');
                if (data.sessions && data.sessions.length > 0) {
                    list.innerHTML = data.sessions.map(s => 
                        `<div class="channel">
                            <span>${s.key}</span>
                            <span>${s.message_count} messages</span>
                        </div>`
                    ).join('');
                    document.getElementById('sessions-count').textContent = data.sessions.length;
                } else {
                    list.innerHTML = '<div>No active sessions</div>';
                    document.getElementById('sessions-count').textContent = '0';
                }
            } catch (e) {
                console.error('Failed to load sessions:', e);
            }
        }
        
        loadStatus();
        loadChannels();
        loadSessions();
        setInterval(loadStatus, 30000);
        setInterval(loadChannels, 60000);
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
    )
    
    if chat_handler:
        server.set_chat_handler(chat_handler)
    
    await server.start()
    return server
