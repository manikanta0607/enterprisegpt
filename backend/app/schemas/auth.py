"""Pydantic request/response models for authentication endpoints."""

from pydantic import BaseModel, Field


class GoogleLoginRequest(BaseModel):
    """Request body for exchanging a Google ID token for platform tokens."""

    id_token: str = Field(..., description="ID token issued by Google Sign-In on the client")
    organization_name: str | None = Field(
        default=None,
        description=(
            "Organization name to create if this is a brand-new user with no "
            "existing organization. Ignored for returning users."
        ),
    )


class RefreshRequest(BaseModel):
    """Request body for refreshing an access token."""

    refresh_token: str = Field(..., description="A valid, unexpired refresh token")


class TokenPairResponse(BaseModel):
    """A pair of access and refresh tokens returned after successful auth."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int = Field(..., description="Access token lifetime in seconds")


class AccessTokenResponse(BaseModel):
    """A single refreshed access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
