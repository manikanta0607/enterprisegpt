"""Role-Based Access Control (RBAC) enforcement.

Provides a FastAPI dependency factory that restricts an endpoint to users
with at least a given role. Composed on top of `get_current_user` from
`app.api.deps`.
"""

from app.core.exceptions import ValidationError
from app.domain.entities import User
from app.domain.enums import Role, role_at_least


class InsufficientRoleError(ValidationError):
    """Raised when a user's role does not meet an endpoint's requirement."""


def require_role(minimum: Role):
    """Build a FastAPI dependency that enforces a minimum role.

    Args:
        minimum: The minimum `Role` required to access the endpoint.

    Returns:
        A dependency callable that raises `InsufficientRoleError` (mapped to
        HTTP 403 by a dedicated handler) if the current user's role is below
        `minimum`, otherwise returns the user unchanged.
    """

    from fastapi import Depends

    from app.api.deps import get_current_user

    def _check(user: User = Depends(get_current_user)) -> User:
        if not role_at_least(user.role, minimum):
            raise InsufficientRoleError(
                f"This action requires the '{minimum.value}' role or higher"
            )
        return user

    return _check
