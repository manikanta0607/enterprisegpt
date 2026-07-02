"""Authentication endpoints: Google login, token refresh, logout."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.schemas.auth import (
    GoogleLoginRequest,
    RefreshRequest,
    TokenPairResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(session: AsyncSession = Depends(get_db_session)) -> AuthService:
    """Provide an `AuthService` bound to the request's DB session."""
    return AuthService(session)


@router.post("/google", response_model=TokenPairResponse, summary="Log in with Google")
async def login_with_google(
    body: GoogleLoginRequest,
    auth_service: AuthService = Depends(_get_auth_service),
) -> TokenPairResponse:
    """Exchange a verified Google ID token for platform access/refresh tokens.

    New users are provisioned automatically as the ADMIN of a new
    organization; returning users simply receive fresh tokens.
    """
    return await auth_service.login_with_google(body.id_token, body.organization_name)


@router.post("/refresh", response_model=TokenPairResponse, summary="Refresh access token")
async def refresh_token(
    body: RefreshRequest,
    auth_service: AuthService = Depends(_get_auth_service),
) -> TokenPairResponse:
    """Exchange a valid refresh token for a new access/refresh token pair."""
    return await auth_service.refresh_access_token(body.refresh_token)


@router.post("/logout", status_code=204, summary="Log out")
async def logout(
    body: RefreshRequest,
    auth_service: AuthService = Depends(_get_auth_service),
) -> None:
    """Revoke a refresh token, ending the associated session."""
    await auth_service.logout(body.refresh_token)
