"""Domain-level enums shared across the application."""

from enum import Enum


class Role(str, Enum):
    """Roles available within an organization, in ascending order of privilege.

    - VIEWER: read-only access to documents and chat.
    - MEMBER: can upload documents and use all knowledge features.
    - ADMIN: full control, including user management and platform settings.
    """

    VIEWER = "viewer"
    MEMBER = "member"
    ADMIN = "admin"


# Ordering used for "at least this role" checks (e.g. require MEMBER or above).
_ROLE_RANK = {Role.VIEWER: 0, Role.MEMBER: 1, Role.ADMIN: 2}


def role_at_least(role: Role, minimum: Role) -> bool:
    """Check whether a role meets or exceeds a minimum required role.

    Args:
        role: The role held by the current user.
        minimum: The minimum role required for the action.

    Returns:
        True if `role` is equal to or more privileged than `minimum`.
    """
    return _ROLE_RANK[role] >= _ROLE_RANK[minimum]


class DocumentStatus(str, Enum):
    """Lifecycle states of an uploaded document as it moves through the
    ingestion pipeline: storage -> parsing -> chunking -> ready for retrieval.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageRole(str, Enum):
    """Who authored a message in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
