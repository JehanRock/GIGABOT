"""
Authentication middleware for FastAPI.

Provides:
- Cookie-based session authentication
- Token authentication fallback
- Auth status and setup endpoints
"""

from typing import Annotated, Any
from datetime import datetime

from fastapi import APIRouter, Request, Response, HTTPException, status, Depends, Cookie
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from nanobot.security.auth import DashboardAuth
from nanobot.server.dependencies import ConfigDep
from nanobot.config.loader import persist_config

router = APIRouter()


# Session storage (in-memory for now, could be Redis in production)
_dashboard_auth: DashboardAuth | None = None


def get_dashboard_auth(config: ConfigDep) -> DashboardAuth:
    """Get or create dashboard auth instance."""
    global _dashboard_auth
    
    if _dashboard_auth is None:
        auth_config = config.security.auth
        _dashboard_auth = DashboardAuth(
            password_hash=auth_config.password_hash,
            password_salt=auth_config.password_salt,
            pin_hash=auth_config.pin_hash,
            pin_salt=auth_config.pin_salt,
            require_pin=auth_config.require_pin,
            session_duration_days=auth_config.session_duration_days,
        )
    
    return _dashboard_auth


DashboardAuthDep = Annotated[DashboardAuth, Depends(get_dashboard_auth)]


async def get_current_session(
    request: Request,
    gigabot_session: str | None = Cookie(default=None),
) -> dict[str, Any] | None:
    """
    Get current session from cookie.
    
    Returns session info if valid, None otherwise.
    """
    if not gigabot_session:
        return None
    
    config = request.app.state.config
    auth = get_dashboard_auth(config)
    
    valid, session = auth.validate_session(gigabot_session)
    if valid and session:
        return session.to_dict()
    
    return None


SessionDep = Annotated[dict[str, Any] | None, Depends(get_current_session)]


class LoginRequest(BaseModel):
    """Login request body."""
    password: str


class PinVerifyRequest(BaseModel):
    """PIN verification request."""
    temp_token: str
    pin: str


class SetupRequest(BaseModel):
    """Auth setup request."""
    password: str
    pin: str | None = None


@router.get("/status")
async def auth_status(
    request: Request,
    config: ConfigDep,
    session: SessionDep,
):
    """Get authentication status."""
    auth = get_dashboard_auth(config)
    
    auth_info = auth.get_auth_status()
    auth_info["authenticated"] = session is not None
    auth_info["session"] = session
    auth_info["setup_complete"] = config.security.auth.setup_complete
    
    return JSONResponse(auth_info)


@router.post("/login")
async def login(
    request: Request,
    login_req: LoginRequest,
    config: ConfigDep,
    response: Response,
):
    """Handle password login."""
    auth = get_dashboard_auth(config)
    
    if not login_req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password required",
        )
    
    # Get client info
    ip_address = request.client.host if request.client else ""
    user_agent = request.headers.get("User-Agent", "")
    
    success, token_or_session, message = auth.login(
        login_req.password, ip_address, user_agent
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )
    
    # Check if PIN is required
    if message == "PIN required":
        return JSONResponse({
            "success": True,
            "require_pin": True,
            "temp_token": token_or_session,
            "message": message,
        })
    
    # No PIN required, session created directly
    response = JSONResponse({
        "success": True,
        "require_pin": False,
        "message": message,
    })
    
    # Set session cookie
    _set_session_cookie(response, token_or_session)
    
    return response


@router.post("/verify-pin")
async def verify_pin(
    request: Request,
    pin_req: PinVerifyRequest,
    config: ConfigDep,
):
    """Handle PIN verification."""
    auth = get_dashboard_auth(config)
    
    if not pin_req.temp_token or not pin_req.pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token and PIN required",
        )
    
    # Get client info
    ip_address = request.client.host if request.client else ""
    user_agent = request.headers.get("User-Agent", "")
    
    success, session_id, message = auth.verify_pin(
        pin_req.temp_token, pin_req.pin, ip_address, user_agent
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )
    
    response = JSONResponse({
        "success": True,
        "message": message,
    })
    
    # Set session cookie
    _set_session_cookie(response, session_id)
    
    return response


@router.post("/logout")
async def logout(
    gigabot_session: str | None = Cookie(default=None),
    config: ConfigDep = None,
):
    """Handle logout."""
    if gigabot_session:
        auth = get_dashboard_auth(config)
        auth.logout(gigabot_session)
    
    response = JSONResponse({"success": True, "message": "Logged out"})
    response.delete_cookie("gigabot_session", path="/")
    
    return response


@router.post("/setup")
async def setup(
    request: Request,
    setup_req: SetupRequest,
    config: ConfigDep,
):
    """Handle initial auth setup."""
    global _dashboard_auth
    
    auth = get_dashboard_auth(config)
    
    # Only allow setup if not already configured
    if config.security.auth.setup_complete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication already configured. Use settings to change password.",
        )
    
    if not setup_req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password required",
        )
    
    if len(setup_req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    
    # Setup password
    password_hash, password_salt = auth.setup_password(setup_req.password)
    
    # Setup PIN if provided
    pin_hash, pin_salt = "", ""
    require_pin = False
    if setup_req.pin:
        if not setup_req.pin.isdigit() or not (4 <= len(setup_req.pin) <= 8):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PIN must be 4-8 digits",
            )
        pin_hash, pin_salt = auth.setup_pin(setup_req.pin)
        require_pin = True
    
    # Update config
    config.security.auth.password_hash = password_hash
    config.security.auth.password_salt = password_salt
    config.security.auth.pin_hash = pin_hash
    config.security.auth.pin_salt = pin_salt
    config.security.auth.require_pin = require_pin
    config.security.auth.setup_complete = True
    config.security.auth.mode = "password"
    
    # Persist config
    try:
        await persist_config(config)
        logger.info("Dashboard auth setup completed and saved to config")
    except Exception as e:
        logger.error(f"Failed to persist config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save configuration: {e}",
        )
    
    # Reset auth instance to pick up new config
    _dashboard_auth = None
    auth = get_dashboard_auth(config)
    
    # Auto-login after setup
    ip_address = request.client.host if request.client else ""
    user_agent = request.headers.get("User-Agent", "")
    
    # Create session directly (skip PIN for initial setup)
    session_id = auth._create_session(ip_address, user_agent)
    
    response = JSONResponse({
        "success": True,
        "message": "Authentication configured",
        "setup_complete": True,
    })
    
    _set_session_cookie(response, session_id)
    
    return response


def _set_session_cookie(response: Response, session_id: str) -> None:
    """Set the session cookie on response."""
    max_age = 7 * 24 * 60 * 60  # 7 days in seconds
    
    response.set_cookie(
        key="gigabot_session",
        value=session_id,
        max_age=max_age,
        httponly=True,
        secure=False,  # Set True for HTTPS only
        samesite="strict",
        path="/",
    )


class AuthMiddleware:
    """
    Authentication middleware for FastAPI.
    
    Checks session cookie for protected routes.
    """
    
    def __init__(self, app, config):
        self.app = app
        self.config = config
        self._auth: DashboardAuth | None = None
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get path
        path = scope.get("path", "")
        
        # Public paths
        public_paths = ["/", "/health", "/favicon.ico", "/favicon.svg"]
        public_prefixes = ["/static", "/assets", "/api/auth/", "/api/system/health"]
        
        if path in public_paths:
            await self.app(scope, receive, send)
            return
        
        for prefix in public_prefixes:
            if path.startswith(prefix):
                await self.app(scope, receive, send)
                return
        
        # Check if auth is configured
        if self._auth is None:
            self._auth = get_dashboard_auth(self.config)
        
        if not self._auth.is_configured:
            # No auth configured, allow access
            await self.app(scope, receive, send)
            return
        
        # Get session cookie from headers
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode()
        
        session_id = None
        for cookie in cookie_header.split("; "):
            if cookie.startswith("gigabot_session="):
                session_id = cookie.split("=", 1)[1]
                break
        
        if session_id:
            valid, _ = self._auth.validate_session(session_id)
            if valid:
                await self.app(scope, receive, send)
                return
        
        # Check for token auth fallback
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer "):
            # Token auth can be implemented here
            pass
        
        # For API routes, return 401
        if path.startswith("/api/"):
            response = Response(
                content='{"error": "Unauthorized", "auth_required": true}',
                status_code=401,
                media_type="application/json",
            )
            await response(scope, receive, send)
            return
        
        # For page requests, allow (SPA will handle login redirect)
        await self.app(scope, receive, send)
