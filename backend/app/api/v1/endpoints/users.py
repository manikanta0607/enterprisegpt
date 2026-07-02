"""User management endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_user_repository
from app.core.rbac import require_role
from app.domain.entities import User
from app.domain.enums import Role
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="Get the current user")
async def get_me(user: User = Depends(get_current_user)) -> User:
    """Return the profile of the currently authenticated user."""
    return user


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List users in the current organization",
)
async def list_organization_users(
    current_user: User = Depends(require_role(Role.ADMIN)),
    user_repository: UserRepository = Depends(get_user_repository),
) -> list[User]:
    """List all users in the caller's organization. Requires the ADMIN role."""
    return await user_repository.list_by_organization(current_user.organization_id)
