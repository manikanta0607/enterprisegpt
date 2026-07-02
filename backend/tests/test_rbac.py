"""Unit tests for RBAC role comparison logic."""

from app.domain.enums import Role, role_at_least


def test_admin_meets_all_minimums():
    """An ADMIN should satisfy every minimum role requirement."""
    assert role_at_least(Role.ADMIN, Role.VIEWER)
    assert role_at_least(Role.ADMIN, Role.MEMBER)
    assert role_at_least(Role.ADMIN, Role.ADMIN)


def test_viewer_only_meets_viewer_minimum():
    """A VIEWER should only satisfy the VIEWER minimum, nothing higher."""
    assert role_at_least(Role.VIEWER, Role.VIEWER)
    assert not role_at_least(Role.VIEWER, Role.MEMBER)
    assert not role_at_least(Role.VIEWER, Role.ADMIN)


def test_member_meets_viewer_and_member_not_admin():
    """A MEMBER should satisfy VIEWER/MEMBER minimums but not ADMIN."""
    assert role_at_least(Role.MEMBER, Role.VIEWER)
    assert role_at_least(Role.MEMBER, Role.MEMBER)
    assert not role_at_least(Role.MEMBER, Role.ADMIN)
