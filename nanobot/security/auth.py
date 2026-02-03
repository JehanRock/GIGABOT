"""
Authentication module for GigaBot gateway.

Supports multiple authentication modes:
- Token: Random token (24+ chars recommended)
- Password: User password with timing-safe comparison
- Tailscale: Identity header verification
- Dashboard: Password + PIN two-factor with cookie sessions
"""

import hmac
import secrets
import hashlib
import time
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


class AuthMode(str, Enum):
    """Authentication mode for gateway."""
    NONE = "none"
    TOKEN = "token"
    PASSWORD = "password"
    TAILSCALE = "tailscale"


@dataclass
class AuthConfig:
    """Authentication configuration."""
    mode: AuthMode = AuthMode.TOKEN
    token: str = ""
    password_hash: str = ""  # SHA-256 hash of password
    tailscale_required_user: str = ""  # Required Tailscale user/node
    
    # Device pairing
    paired_devices: list[str] = field(default_factory=list)
    require_pairing: bool = False


@dataclass
class DeviceAuth:
    """Device authentication payload (versioned)."""
    version: int  # v1 = basic, v2 = with nonce
    device_id: str
    timestamp: int  # Unix timestamp in ms
    signature: str
    nonce: str = ""  # v2 only, prevents replay attacks


def generate_token(length: int = 32) -> str:
    """
    Generate a secure random token.
    
    Args:
        length: Token length in characters (default 32).
    
    Returns:
        URL-safe base64 encoded token.
    """
    return secrets.token_urlsafe(length)


def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256.
    
    Args:
        password: Plain text password.
    
    Returns:
        Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(password.encode()).hexdigest()


def verify_token(provided: str, expected: str) -> bool:
    """
    Verify a token using timing-safe comparison.
    
    Args:
        provided: Token provided by client.
        expected: Expected token from config.
    
    Returns:
        True if tokens match.
    """
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


def verify_password(provided: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        provided: Plain text password from client.
        password_hash: Stored SHA-256 hash.
    
    Returns:
        True if password matches.
    """
    if not provided or not password_hash:
        return False
    provided_hash = hash_password(provided)
    return hmac.compare_digest(provided_hash.encode(), password_hash.encode())


def verify_tailscale_identity(
    headers: dict[str, str],
    required_user: str = ""
) -> tuple[bool, str]:
    """
    Verify Tailscale identity from headers.
    
    Tailscale sets these headers when proxying:
    - Tailscale-User-Login: user@domain
    - Tailscale-User-Name: Display Name
    - Tailscale-User-Profile-Pic: URL
    
    Args:
        headers: Request headers.
        required_user: If set, require this specific user.
    
    Returns:
        Tuple of (verified, user_login).
    """
    user_login = headers.get("Tailscale-User-Login", "")
    
    if not user_login:
        return False, ""
    
    if required_user and user_login != required_user:
        return False, user_login
    
    return True, user_login


def authenticate_request(
    config: AuthConfig,
    headers: dict[str, str],
    provided_token: str = "",
    provided_password: str = "",
) -> tuple[bool, str]:
    """
    Authenticate an incoming request based on config mode.
    
    Args:
        config: Authentication configuration.
        headers: Request headers.
        provided_token: Token from request (Authorization header or query).
        provided_password: Password from request.
    
    Returns:
        Tuple of (authenticated, identity).
        Identity is the user/device identifier if authenticated.
    """
    if config.mode == AuthMode.NONE:
        return True, "anonymous"
    
    if config.mode == AuthMode.TOKEN:
        if verify_token(provided_token, config.token):
            return True, "token_auth"
        return False, ""
    
    if config.mode == AuthMode.PASSWORD:
        if verify_password(provided_password, config.password_hash):
            return True, "password_auth"
        return False, ""
    
    if config.mode == AuthMode.TAILSCALE:
        verified, user = verify_tailscale_identity(
            headers, config.tailscale_required_user
        )
        if verified:
            return True, user
        return False, ""
    
    return False, ""


def verify_device_auth(
    payload: DeviceAuth,
    secret: str,
    max_age_ms: int = 30000,
    used_nonces: set[str] | None = None,
) -> tuple[bool, str]:
    """
    Verify device authentication payload.
    
    Args:
        payload: Device auth payload.
        secret: Shared secret for signature verification.
        max_age_ms: Maximum age of timestamp (default 30s).
        used_nonces: Set of used nonces (for replay protection).
    
    Returns:
        Tuple of (verified, error_message).
    """
    import time
    
    current_time = int(time.time() * 1000)
    
    # Check timestamp age
    age = abs(current_time - payload.timestamp)
    if age > max_age_ms:
        return False, "Timestamp expired"
    
    # Check nonce for v2
    if payload.version >= 2:
        if not payload.nonce:
            return False, "Nonce required for v2"
        if used_nonces is not None:
            if payload.nonce in used_nonces:
                return False, "Nonce already used"
            used_nonces.add(payload.nonce)
    
    # Verify signature
    if payload.version == 1:
        message = f"{payload.device_id}:{payload.timestamp}"
    else:
        message = f"{payload.device_id}:{payload.timestamp}:{payload.nonce}"
    
    expected_sig = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(payload.signature, expected_sig):
        return False, "Invalid signature"
    
    return True, ""


def create_device_auth(
    device_id: str,
    secret: str,
    version: int = 2,
) -> DeviceAuth:
    """
    Create a device authentication payload.
    
    Args:
        device_id: Unique device identifier.
        secret: Shared secret for signing.
        version: Payload version (1 or 2).
    
    Returns:
        DeviceAuth payload ready for transmission.
    """
    import time
    
    timestamp = int(time.time() * 1000)
    nonce = secrets.token_hex(16) if version >= 2 else ""
    
    if version == 1:
        message = f"{device_id}:{timestamp}"
    else:
        message = f"{device_id}:{timestamp}:{nonce}"
    
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return DeviceAuth(
        version=version,
        device_id=device_id,
        timestamp=timestamp,
        signature=signature,
        nonce=nonce,
    )


# ========================================
# Dashboard Authentication (Password + PIN)
# ========================================

@dataclass
class SessionInfo:
    """Information about an active session."""
    session_id: str
    created_at: datetime
    expires_at: datetime
    user_agent: str = ""
    ip_address: str = ""
    last_activity: datetime = field(default_factory=datetime.now)
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now() >= self.expires_at
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "last_activity": self.last_activity.isoformat(),
        }


@dataclass 
class PendingAuth:
    """Pending authentication waiting for PIN verification."""
    temp_token: str
    created_at: datetime
    expires_at: datetime  # Short expiry (5 minutes)
    ip_address: str = ""
    
    def is_expired(self) -> bool:
        """Check if pending auth has expired."""
        return datetime.now() >= self.expires_at


def hash_with_salt(value: str, salt: str) -> str:
    """
    Hash a value with salt using SHA-256.
    
    Args:
        value: Value to hash (password or PIN).
        salt: Salt string.
    
    Returns:
        Hex-encoded SHA-256 hash.
    """
    salted = f"{salt}:{value}"
    return hashlib.sha256(salted.encode()).hexdigest()


def generate_salt() -> str:
    """Generate a random salt."""
    return secrets.token_hex(16)


def verify_hash(value: str, stored_hash: str, salt: str) -> bool:
    """
    Verify a value against its salted hash.
    
    Args:
        value: Plain text value.
        stored_hash: Stored SHA-256 hash.
        salt: Salt used for hashing.
    
    Returns:
        True if value matches.
    """
    if not value or not stored_hash or not salt:
        return False
    computed_hash = hash_with_salt(value, salt)
    return hmac.compare_digest(computed_hash.encode(), stored_hash.encode())


class DashboardAuth:
    """
    Dashboard authentication with password + PIN two-factor.
    
    Flow:
    1. User enters password
    2. If valid, returns temporary token
    3. User enters PIN with temp token
    4. If valid, creates session with cookie
    5. Session valid for configured duration (default 7 days)
    """
    
    def __init__(
        self,
        password_hash: str = "",
        password_salt: str = "",
        pin_hash: str = "",
        pin_salt: str = "",
        require_pin: bool = True,
        session_duration_days: int = 7,
    ):
        self.password_hash = password_hash
        self.password_salt = password_salt
        self.pin_hash = pin_hash
        self.pin_salt = pin_salt
        self.require_pin = require_pin
        self.session_duration = timedelta(days=session_duration_days)
        
        # Active sessions
        self._sessions: dict[str, SessionInfo] = {}
        
        # Pending authentications (waiting for PIN)
        self._pending_auth: dict[str, PendingAuth] = {}
        
        # PIN entry timeout (5 minutes)
        self._pin_timeout = timedelta(minutes=5)
    
    @property
    def is_configured(self) -> bool:
        """Check if authentication is configured (password set)."""
        return bool(self.password_hash and self.password_salt)
    
    @property
    def is_pin_configured(self) -> bool:
        """Check if PIN is configured."""
        return bool(self.pin_hash and self.pin_salt)
    
    def setup_password(self, password: str) -> tuple[str, str]:
        """
        Set up a new password.
        
        Args:
            password: New password (min 8 characters).
        
        Returns:
            Tuple of (hash, salt) to store in config.
        
        Raises:
            ValueError: If password is too short.
        """
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        salt = generate_salt()
        password_hash = hash_with_salt(password, salt)
        
        self.password_hash = password_hash
        self.password_salt = salt
        
        return password_hash, salt
    
    def setup_pin(self, pin: str) -> tuple[str, str]:
        """
        Set up a new PIN.
        
        Args:
            pin: New PIN (4-8 digits).
        
        Returns:
            Tuple of (hash, salt) to store in config.
        
        Raises:
            ValueError: If PIN is invalid.
        """
        if not pin.isdigit() or not (4 <= len(pin) <= 8):
            raise ValueError("PIN must be 4-8 digits")
        
        salt = generate_salt()
        pin_hash = hash_with_salt(pin, salt)
        
        self.pin_hash = pin_hash
        self.pin_salt = salt
        
        return pin_hash, salt
    
    def login(
        self,
        password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> tuple[bool, str, str]:
        """
        Verify password and start authentication flow.
        
        Args:
            password: User's password.
            ip_address: Client IP address.
            user_agent: Client user agent.
        
        Returns:
            Tuple of (success, temp_token_or_session_id, message).
            If PIN is required, returns temp_token.
            If PIN not required, creates session and returns session_id.
        """
        # Clean up expired pending auths
        self._cleanup_pending()
        
        if not self.is_configured:
            return False, "", "Authentication not configured"
        
        if not verify_hash(password, self.password_hash, self.password_salt):
            return False, "", "Invalid password"
        
        # If PIN not required, create session directly
        if not self.require_pin or not self.is_pin_configured:
            session_id = self._create_session(ip_address, user_agent)
            return True, session_id, "Login successful"
        
        # Create pending auth for PIN verification
        temp_token = secrets.token_urlsafe(32)
        now = datetime.now()
        
        self._pending_auth[temp_token] = PendingAuth(
            temp_token=temp_token,
            created_at=now,
            expires_at=now + self._pin_timeout,
            ip_address=ip_address,
        )
        
        return True, temp_token, "PIN required"
    
    def verify_pin(
        self,
        temp_token: str,
        pin: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> tuple[bool, str, str]:
        """
        Verify PIN and create session.
        
        Args:
            temp_token: Temporary token from password step.
            pin: User's PIN.
            ip_address: Client IP address.
            user_agent: Client user agent.
        
        Returns:
            Tuple of (success, session_id, message).
        """
        # Clean up expired pending auths
        self._cleanup_pending()
        
        # Check temp token
        pending = self._pending_auth.get(temp_token)
        if not pending:
            return False, "", "Invalid or expired temporary token"
        
        if pending.is_expired():
            del self._pending_auth[temp_token]
            return False, "", "PIN entry timeout"
        
        # Optionally check IP matches
        if pending.ip_address and pending.ip_address != ip_address:
            # IP changed, might be session hijack attempt
            del self._pending_auth[temp_token]
            return False, "", "Session security error"
        
        # Verify PIN
        if not verify_hash(pin, self.pin_hash, self.pin_salt):
            return False, "", "Invalid PIN"
        
        # Remove pending auth
        del self._pending_auth[temp_token]
        
        # Create session
        session_id = self._create_session(ip_address, user_agent)
        return True, session_id, "Login successful"
    
    def _create_session(self, ip_address: str, user_agent: str) -> str:
        """Create a new session."""
        session_id = secrets.token_urlsafe(32)
        now = datetime.now()
        
        self._sessions[session_id] = SessionInfo(
            session_id=session_id,
            created_at=now,
            expires_at=now + self.session_duration,
            user_agent=user_agent,
            ip_address=ip_address,
            last_activity=now,
        )
        
        return session_id
    
    def validate_session(self, session_id: str) -> tuple[bool, SessionInfo | None]:
        """
        Validate a session.
        
        Args:
            session_id: Session ID from cookie.
        
        Returns:
            Tuple of (valid, session_info).
        """
        # Clean up expired sessions
        self._cleanup_sessions()
        
        session = self._sessions.get(session_id)
        if not session:
            return False, None
        
        if session.is_expired():
            del self._sessions[session_id]
            return False, None
        
        # Update last activity
        session.last_activity = datetime.now()
        
        return True, session
    
    def logout(self, session_id: str) -> bool:
        """
        Invalidate a session.
        
        Args:
            session_id: Session ID to invalidate.
        
        Returns:
            True if session was found and removed.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get list of active sessions."""
        self._cleanup_sessions()
        return [s.to_dict() for s in self._sessions.values()]
    
    def logout_all(self) -> int:
        """
        Logout all sessions.
        
        Returns:
            Number of sessions invalidated.
        """
        count = len(self._sessions)
        self._sessions.clear()
        return count
    
    def _cleanup_pending(self) -> None:
        """Remove expired pending authentications."""
        expired = [
            token for token, pending in self._pending_auth.items()
            if pending.is_expired()
        ]
        for token in expired:
            del self._pending_auth[token]
    
    def _cleanup_sessions(self) -> None:
        """Remove expired sessions."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        for sid in expired:
            del self._sessions[sid]
    
    def get_auth_status(self) -> dict[str, Any]:
        """Get authentication status information."""
        return {
            "configured": self.is_configured,
            "pin_configured": self.is_pin_configured,
            "require_pin": self.require_pin,
            "session_duration_days": self.session_duration.days,
            "active_sessions": len(self._sessions),
        }
