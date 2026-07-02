"""Unit tests for JWT token creation and verification."""

import uuid

import pytest

from app.core.exceptions import ValidationError
from app.core.security import TokenType, create_token, decode_token


def test_create_and_decode_access_token():
    """An access token should encode and decode with the correct claims."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    token, expires_at = create_token(
        subject=user_id, role="member", organization_id=org_id, token_type=TokenType.ACCESS
    )
    payload = decode_token(token, expected_type=TokenType.ACCESS)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "member"
    assert payload["org_id"] == str(org_id)
    assert payload["type"] == "access"
    assert expires_at is not None


def test_decode_rejects_wrong_token_type():
    """Decoding an access token while expecting a refresh token should fail."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    token, _ = create_token(
        subject=user_id, role="admin", organization_id=org_id, token_type=TokenType.ACCESS
    )

    with pytest.raises(ValidationError):
        decode_token(token, expected_type=TokenType.REFRESH)


def test_decode_rejects_malformed_token():
    """Decoding a garbage string should raise ValidationError, not crash."""
    with pytest.raises(ValidationError):
        decode_token("not.a.valid.jwt", expected_type=TokenType.ACCESS)
