"""
FastAPI application factory for GigaBot.

Provides:
- Application creation with proper lifecycle management
- Router registration
- Static file serving for React dashboard
- CORS and middleware configuration
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from nanobot.server.agent_manager import AgentManager
from nanobot.server.routers import (
    system_router,
    chat_router,
    providers_router,
    config_router,
    gateways_router,
)
from nanobot.server.middleware.auth import router as auth_router

if TYPE_CHECKING:
    from nanobot.config.schema import Config
    from nanobot.channels.manager import ChannelManager
    from nanobot.nodes.manager import NodeManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown:
    - Startup: Initialize AgentManager, attempt connection
    - Shutdown: Cleanup resources
    """
    logger.info("Starting GigaBot server...")
    
    # Get config from app state (set before lifespan)
    config = app.state.config
    workspace = app.state.workspace
    
    # Create and initialize agent manager
    agent_manager = AgentManager(
        config=config,
        workspace=workspace,
    )
    app.state.agent_manager = agent_manager
    
    # Try to initialize agent (may fail if no API key)
    await agent_manager.initialize()
    
    logger.info(f"Agent state: {agent_manager.state.value}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down GigaBot server...")
    await agent_manager.shutdown()


def create_app(
    config: "Config",
    workspace: Path,
    channels: "ChannelManager | None" = None,
    node_manager: "NodeManager | None" = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        config: GigaBot configuration
        workspace: Workspace path
        channels: Optional channel manager
        node_manager: Optional node manager
    
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="GigaBot API",
        description="Enterprise-grade AI assistant API",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # Store config in app state (before lifespan)
    app.state.config = config
    app.state.workspace = workspace
    app.state.channels = channels
    app.state.node_manager = node_manager
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routers
    app.include_router(system_router, prefix="/api/system", tags=["System"])
    app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
    app.include_router(providers_router, prefix="/api/providers", tags=["Providers"])
    app.include_router(config_router, prefix="/api/config", tags=["Config"])
    app.include_router(gateways_router, prefix="/api/gateways", tags=["Gateways"])
    app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    
    # Legacy routes (for backward compatibility)
    _add_legacy_routes(app)
    
    # WebSocket at root level for backward compatibility
    _add_websocket_routes(app)
    
    # Serve React dashboard static files
    _setup_static_files(app)
    
    return app


def _add_legacy_routes(app: FastAPI):
    """Add legacy routes for backward compatibility."""
    from fastapi import Request
    from fastapi.responses import JSONResponse
    
    @app.get("/api/status")
    async def legacy_status(request: Request):
        """Legacy status endpoint."""
        agent_manager = request.app.state.agent_manager
        config = request.app.state.config
        channels = request.app.state.channels
        
        status = {
            "status": "running",
            "version": "0.1.0",
            "model": config.agents.defaults.model,
            "workspace": str(request.app.state.workspace),
        }
        
        # Add agent status
        status.update(agent_manager.get_status())
        
        # Add channel status
        if channels:
            status["channels"] = channels.get_status()
        
        # Add tracking if available
        if agent_manager.tracker:
            status["tracking"] = agent_manager.tracker.get_summary()
        
        return JSONResponse(status)
    
    @app.get("/api/sessions")
    async def legacy_sessions(request: Request):
        """Legacy sessions endpoint."""
        agent_manager = request.app.state.agent_manager
        
        if not agent_manager.sessions:
            return JSONResponse({"sessions": []})
        
        sessions = agent_manager.sessions.list_sessions()
        result = []
        
        for s in sessions:
            if isinstance(s, dict):
                result.append({
                    "key": s.get("key", "unknown"),
                    "message_count": len(s.get("messages", [])),
                    "last_updated": s.get("updated_at"),
                })
            else:
                result.append({
                    "key": getattr(s, "key", "unknown"),
                    "message_count": len(getattr(s, "messages", [])),
                    "last_updated": s.updated_at.isoformat() if hasattr(s, "updated_at") else None,
                })
        
        return JSONResponse({"sessions": result})
    
    @app.get("/api/tracking")
    async def legacy_tracking(request: Request):
        """Legacy tracking endpoint."""
        agent_manager = request.app.state.agent_manager
        
        if not agent_manager.tracker:
            return JSONResponse({"error": "Tracking not enabled"})
        
        return JSONResponse(agent_manager.tracker.get_summary())
    
    @app.get("/api/channels")
    async def legacy_channels(request: Request):
        """Legacy channels endpoint."""
        channels = request.app.state.channels
        
        if not channels:
            return JSONResponse({"channels": {}})
        
        return JSONResponse({"channels": channels.get_status()})
    
    @app.get("/api/memory")
    async def legacy_memory(request: Request):
        """Legacy memory endpoint."""
        return JSONResponse({
            "daily_notes": 0,
            "long_term_entries": 0,
            "vector_store_size": 0,
        })
    
    @app.get("/api/nodes")
    async def legacy_nodes(request: Request):
        """Legacy nodes endpoint."""
        node_manager = request.app.state.node_manager
        
        if not node_manager:
            return JSONResponse({
                "nodes": [],
                "enabled": False,
            })
        
        nodes = node_manager.list_nodes()
        pending = node_manager.list_pending()
        
        return JSONResponse({
            "nodes": [n.to_dict() for n in nodes],
            "pending": [n.to_dict() for n in pending],
            "enabled": True,
            "connected_count": sum(1 for n in nodes if node_manager.is_connected(n.id)),
        })
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return JSONResponse({"status": "ok"})


def _add_websocket_routes(app: FastAPI):
    """Add WebSocket routes at root level for backward compatibility."""
    from fastapi import WebSocket, WebSocketDisconnect
    import json
    import uuid
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for streaming chat."""
        await websocket.accept()
        client_id = str(uuid.uuid4())[:8]
        logger.info(f"WebSocket client connected: {client_id}")
        
        agent_manager = websocket.app.state.agent_manager
        
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action", "")
                
                if action == "chat":
                    message = data.get("message", "")
                    session_id = data.get("session_id", f"webui:{client_id}")
                    
                    # Send typing indicator
                    await websocket.send_json({"type": "typing", "status": True})
                    
                    try:
                        if not agent_manager.is_ready:
                            await websocket.send_json({
                                "type": "response",
                                "content": agent_manager.get_not_ready_message(),
                                "session_id": session_id,
                            })
                        else:
                            response = await agent_manager.handle_chat(message, session_id)
                            await websocket.send_json({
                                "type": "response",
                                "content": response,
                                "session_id": session_id,
                            })
                    except Exception as e:
                        logger.error(f"Chat error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "error": str(e),
                        })
                    finally:
                        await websocket.send_json({"type": "typing", "status": False})
                
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif action == "status":
                    status = agent_manager.get_status()
                    await websocket.send_json({"type": "status", "data": status})
                
                elif action == "abort":
                    await websocket.send_json({"type": "aborted"})
                
                else:
                    await websocket.send_json({"type": "error", "error": f"Unknown action: {action}"})
        
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")


def _setup_static_files(app: FastAPI):
    """Setup static file serving for React dashboard."""
    from fastapi.responses import FileResponse, HTMLResponse
    
    dist_dir = Path(__file__).parent.parent / "ui" / "dist"
    
    @app.get("/favicon.svg")
    @app.get("/favicon.ico")
    async def favicon():
        """Serve favicon."""
        favicon_path = dist_dir / "favicon.svg"
        if favicon_path.exists():
            return FileResponse(favicon_path)
        
        # Fallback SVG
        return HTMLResponse(
            content='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="#6366f1" width="100" height="100" rx="20"/><text x="50" y="68" font-family="Arial" font-size="50" font-weight="bold" fill="white" text-anchor="middle">G</text></svg>',
            media_type="image/svg+xml"
        )
    
    # Serve static assets if dist exists
    if dist_dir.exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    @app.get("/")
    async def index():
        """Serve dashboard index."""
        index_path = dist_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        # Simple error page
        return HTMLResponse(
            content="""<!DOCTYPE html>
<html>
<head><title>GigaBot</title></head>
<body style="background:#0f0f1a;color:#fff;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;">
<div style="text-align:center;">
<h1 style="color:#6366f1;">GigaBot Dashboard</h1>
<p>Dashboard not built. Run:</p>
<code style="background:#1a1a2e;padding:8px 16px;border-radius:8px;display:block;margin:16px 0;">cd nanobot/ui/dashboard && npm run build</code>
</div>
</body>
</html>""",
            status_code=503,
        )
    
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        """SPA fallback - serve index.html for client-side routing."""
        # Don't intercept API or WebSocket routes
        if path.startswith(("api/", "ws")):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        
        # Try to serve as static file first
        file_path = dist_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # Serve index.html for SPA routing
        index_path = dist_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        # Simple error
        return HTMLResponse(
            content="<h1>Not Found</h1>",
            status_code=404,
        )
