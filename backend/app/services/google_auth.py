"""Verification of Google-issued ID tokens.

Isolated into its own module so the auth service — and its tests — don't
need to depend directly on the `google-auth` library's request internals.
"""

from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings
from app.core.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    """Verified identity claims extracted from a Google ID token."""

    sub: str
    email: str
    full_name: str
    email_verified: bool


def verify_google_id_token(raw_token: str) -> GoogleProfile:
    """Verify a Google ID token's signature, audience, and issuer.

    Args:
        raw_token: The raw ID token string received from the client.

    Returns:
        A `GoogleProfile` with the verified identity claims.

    Raises:
        ValidationError: If the token is invalid, expired, or was not
            issued for this application's Google OAuth client.
    """
    settings = get_settings()
    try:
        claims = google_id_token.verify_oauth2_token(
            raw_token, google_requests.Request(), settings.google_client_id
        )
    except ValueError as exc:
        raise ValidationError("Invalid Google ID token") from exc

    if not claims.get("email_verified", False):
        raise ValidationError("Google account email is not verified")

    return GoogleProfile(
        sub=claims["sub"],
        email=claims["email"],
        full_name=claims.get("name", claims["email"]),
        email_verified=True,
    )
