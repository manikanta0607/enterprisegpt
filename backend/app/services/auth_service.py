"""Authentication service: Google login, token issuance, refresh, and revocation.

This is the only layer that coordinates across the user/organization
repositories and the token/Google-verification utilities — endpoints call
into this service and never touch repositories or JWT internals directly.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.security import TokenType, create_token, decode_token
from app.domain.entities import User
from app.infrastructure.database.models import RefreshTokenModel
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPairResponse
from app.services.google_auth import verify_google_id_token


class AuthService:
    """Coordinates Google authentication and JWT lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a request-scoped DB session.

        Args:
            session: The active `AsyncSession` for this request.
        """
        self._session = session
        self._users = UserRepository(session)
        self._orgs = OrganizationRepository(session)

    async def login_with_google(
        self, id_token: str, organization_name: str | None
    ) -> TokenPairResponse:
        """Authenticate a user via Google, creating their account if new.

        A brand-new user creates a new organization (named `organization_name`
        if provided, else derived from their email domain) and is made its
        first ADMIN. Returning users are simply issued fresh tokens.

        Args:
            id_token: The raw Google ID token from the client.
            organization_name: Organization name to use if this is a new user.

        Returns:
            A `TokenPairResponse` with a fresh access and refresh token.
        """
        from app.domain.enums import Role

        profile = verify_google_id_token(id_token)

        user = await self._users.get_by_google_sub(profile.sub)

        if user is None:
            org_name = organization_name or profile.email.split("@")[-1]
            organization = await self._orgs.create(name=org_name)
            user = await self._users.create(
                email=profile.email,
                full_name=profile.full_name,
                google_sub=profile.sub,
                organization_id=organization.id,
                role=Role.ADMIN,
            )
            await self._session.commit()
        elif not user.is_active:
            raise ValidationError("This account has been deactivated")

        return await self._issue_token_pair(user)

    async def refresh_access_token(self, refresh_token: str) -> TokenPairResponse:
        """Exchange a valid, unrevoked refresh token for a new token pair.

        Implements refresh token rotation: the old refresh token is revoked
        and a new one issued, limiting the blast radius of a leaked token.

        Args:
            refresh_token: The raw refresh token string.

        Returns:
            A new `TokenPairResponse`.

        Raises:
            ValidationError: If the token is invalid, expired, or revoked.
        """
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)

        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token == refresh_token)
        )
        stored = result.scalar_one_or_none()

        if stored is None or stored.revoked:
            raise ValidationError("Refresh token has been revoked or does not exist")
        if stored.expires_at < datetime.now(timezone.utc):
            raise ValidationError("Refresh token has expired")

        import uuid as _uuid

        user = await self._users.get_by_id(_uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            raise ValidationError("User account is no longer active")

        stored.revoked = True
        pair = await self._issue_token_pair(user)
        await self._session.commit()
        return pair

    async def logout(self, refresh_token: str) -> None:
        """Revoke a refresh token, ending the associated session.

        Args:
            refresh_token: The raw refresh token string to revoke.
        """
        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token == refresh_token)
        )
        stored = result.scalar_one_or_none()
        if stored is not None:
            stored.revoked = True
            await self._session.commit()

    async def _issue_token_pair(self, user: User) -> TokenPairResponse:
        """Create and persist a fresh access + refresh token pair for a user.

        Args:
            user: The authenticated user.

        Returns:
            A `TokenPairResponse` with both tokens.
        """
        from app.core.config import get_settings

        settings = get_settings()

        access_token, _ = create_token(
            subject=user.id,
            role=user.role.value,
            organization_id=user.organization_id,
            token_type=TokenType.ACCESS,
        )
        refresh_token, refresh_expires_at = create_token(
            subject=user.id,
            role=user.role.value,
            organization_id=user.organization_id,
            token_type=TokenType.REFRESH,
        )

        self._session.add(
            RefreshTokenModel(
                user_id=user.id, token=refresh_token, expires_at=refresh_expires_at
            )
        )
        await self._session.commit()

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in_seconds=settings.access_token_expire_minutes * 60,
        )
