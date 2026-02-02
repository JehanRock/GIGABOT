"""
Authentication module for GigaBot gateway.

Supports multiple authentication modes:
- Token: Random token (24+ chars recommended)
- Password: User password with timing-safe comparison
- Tailscale: Identity header verification
"""

import hmac
import secrets
import hashlib
from enum import Enum
from dataclasses import dataclass, field
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
