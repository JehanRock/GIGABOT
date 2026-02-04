"""
Chat routes for GigaBot API.

Provides:
- /api/chat - Send message and get response
- /ws/chat - WebSocket for streaming chat
"""

import json
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from nanobot.server.dependencies import AgentManagerDep, ReadyAgentDep

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request body."""
    message: str
    session_id: str = "webui:default"


class ChatResponse(BaseModel):
    """Chat response body."""
    response: str
    session_id: str


@router.post("", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    agent_manager: ReadyAgentDep,
):
    """
    Send a chat message and get a response.
    
    Requires agent to be ready (API key configured).
    """
    response = await agent_manager.handle_chat(
        message=request.message,
        session_id=request.session_id,
    )
    
    return ChatResponse(
        response=response,
        session_id=request.session_id,
    )


@router.get("/status")
async def chat_status(agent_manager: AgentManagerDep):
    """
    Get chat availability status.
    
    Returns whether chat is available and why if not.
    """
    return JSONResponse({
        "available": agent_manager.is_ready,
        "agent_state": agent_manager.state.value,
        "message": None if agent_manager.is_ready else agent_manager.get_not_ready_message(),
    })


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
    
    async def send_json(self, client_id: str, data: dict[str, Any]):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)
    
    async def broadcast(self, data: dict[str, Any]):
        for connection in self.active_connections.values():
            await connection.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    request: Request,
):
    """
    WebSocket endpoint for streaming chat.
    
    Supports:
    - action: "chat" - Send message
    - action: "ping" - Keep alive
    - action: "status" - Get status
    - action: "abort" - Abort current request
    """
    # Generate unique client ID
    import uuid
    client_id = str(uuid.uuid4())[:8]
    
    await manager.connect(websocket, client_id)
    logger.info(f"WebSocket client connected: {client_id}")
    
    agent_manager = request.app.state.agent_manager
    
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
                # TODO: Implement abort functionality
                await websocket.send_json({"type": "aborted"})
            
            else:
                await websocket.send_json({"type": "error", "error": f"Unknown action: {action}"})
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(client_id)
