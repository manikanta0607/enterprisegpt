"""JWT access/refresh token creation and verification.

Access tokens are short-lived and carry the user's identity + role for
authorization checks. Refresh tokens are long-lived, opaque-to-the-client
JWTs whose validity is additionally checked against the `refresh_tokens`
table (so they can be revoked before their natural expiry).
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import ValidationError


class TokenType(str, Enum):
    """Distinguishes access tokens from refresh tokens in the JWT payload."""

    ACCESS = "access"
    REFRESH = "refresh"


def create_token(
    *, subject: uuid.UUID, role: str, organization_id: uuid.UUID, token_type: TokenType
) -> tuple[str, datetime]:
    """Create a signed JWT for the given user.

    Args:
        subject: The user's UUID, stored as the `sub` claim.
        role: The user's role, stored as a custom claim for authorization.
        organization_id: The user's organization UUID, stored as a custom claim.
        token_type: Whether this is an access or refresh token, which
            determines its lifetime.

    Returns:
        A tuple of (encoded JWT string, expiry datetime in UTC).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if token_type is TokenType.ACCESS:
        expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    else:
        expires_at = now + timedelta(days=settings.refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "org_id": str(organization_id),
        "type": token_type.value,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    """Decode and validate a JWT, checking its type matches what's expected.

    Args:
        token: The encoded JWT string.
        expected_type: The token type the caller expects (access or refresh),
            preventing an access token from being used where a refresh token
            is required, and vice versa.

    Returns:
        The decoded token payload.

    Raises:
        ValidationError: If the token is malformed, expired, or of the wrong type.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValidationError("Invalid or expired token") from exc

    if payload.get("type") != expected_type.value:
        raise ValidationError(f"Expected a {expected_type.value} token")

    return payload
