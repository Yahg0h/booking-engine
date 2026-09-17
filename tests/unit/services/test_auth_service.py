"""
Unit tests for auth_service.py

Pure functions (create_jwt_token, decode_token) tested directly.
Async functions (authenticate_user, verify_user_token) use mocks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.services.auth_service import (
    authenticate_user,
    create_jwt_token,
    decode_token,
    get_current_user_optional,
    verify_user_token,
)

# ==========================================
# create_jwt_token
# ==========================================

def test_create_jwt_token_returns_string():
    token = create_jwt_token(user_id=1)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_jwt_token_is_decodable():
    token = create_jwt_token(user_id=42)
    user_id = decode_token(token)
    assert user_id == 42


def test_create_jwt_token_different_users_produce_different_tokens():
    token_a = create_jwt_token(user_id=1)
    token_b = create_jwt_token(user_id=2)
    assert token_a != token_b


# ==========================================
# decode_token
# ==========================================

def test_decode_token_returns_correct_user_id():
    token = create_jwt_token(user_id=99)
    assert decode_token(token) == 99


def test_decode_token_invalid_token_raises_value_error():
    with pytest.raises(ValueError, match="Token decoding failed"):
        decode_token("this.is.not.a.valid.token")


def test_decode_token_expired_raises_value_error():
    # Generate token that expired instantly using ignore_exp=False
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.config import settings

    payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1)  # already expired
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET, settings.ALGORITHM)

    with pytest.raises(ValueError, match="Token decoding failed"):
        decode_token(expired_token, ignore_exp=False)


def test_decode_token_ignore_exp_accepts_expired():
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.config import settings

    payload = {
        "sub": "7",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1)
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET, settings.ALGORITHM)

    user_id = decode_token(expired_token, ignore_exp=True)
    assert user_id == 7


def test_decode_token_missing_sub_raises_value_error():
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.config import settings

    payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
    token = jwt.encode(payload, settings.JWT_SECRET, settings.ALGORITHM)

    with pytest.raises(ValueError, match="Invalid Token"):
        decode_token(token)


# ==========================================
# verify_user_token
# ==========================================

@pytest.mark.asyncio
async def test_verify_user_token_valid_bearer():
    token = create_jwt_token(user_id=5)
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}

    user_id = await verify_user_token(request)
    assert user_id == 5


@pytest.mark.asyncio
async def test_verify_user_token_missing_header_raises_401():
    request = MagicMock()
    request.headers = {}

    with pytest.raises(HTTPException) as exc:
        await verify_user_token(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_user_token_wrong_scheme_raises_401():
    request = MagicMock()
    request.headers = {"Authorization": "Basic sometoken"}

    with pytest.raises(HTTPException) as exc:
        await verify_user_token(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_user_token_invalid_token_raises_401():
    request = MagicMock()
    request.headers = {"Authorization": "Bearer invalid.token.here"}

    with pytest.raises(HTTPException) as exc:
        await verify_user_token(request)
    assert exc.value.status_code == 401


# ==========================================
# get_current_user_optional
# ==========================================

@pytest.mark.asyncio
async def test_get_current_user_optional_no_header_returns_none():
    request = MagicMock()
    request.headers = {}

    result = await get_current_user_optional(request)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_user_optional_valid_token_returns_id():
    token = create_jwt_token(user_id=3)
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}

    result = await get_current_user_optional(request)
    assert result == 3


@pytest.mark.asyncio
async def test_get_current_user_optional_invalid_token_returns_none():
    request = MagicMock()
    request.headers = {"Authorization": "Bearer garbage"}

    result = await get_current_user_optional(request)
    assert result is None


# ==========================================
# authenticate_user
# ==========================================

FAKE_USER = {
    "id": 10,
    "email": "test@example.com",
    # Argon2 hash of "correct_password" — pre-computed for test isolation
    "password_hash": None,  # will be set in fixture
}


@pytest.mark.asyncio
async def test_authenticate_user_correct_credentials_returns_id():
    from app.api.v1.services.password_service import hash_password

    hashed = hash_password("correct_password")
    fake_user = {"id": 10, "email": "test@example.com", "password_hash": hashed}

    with patch("app.api.v1.services.auth_service.search_user_by_email",
               new=AsyncMock(return_value=fake_user)):
        result = await authenticate_user("test@example.com", "correct_password")
    assert result == 10


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password_returns_none():
    from app.api.v1.services.password_service import hash_password

    hashed = hash_password("correct_password")
    fake_user = {"id": 10, "email": "test@example.com", "password_hash": hashed}

    with patch("app.api.v1.services.auth_service.search_user_by_email",
               new=AsyncMock(return_value=fake_user)):
        result = await authenticate_user("test@example.com", "wrong_password")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_email_not_found_raises_value_error():
    with patch("app.api.v1.services.auth_service.search_user_by_email",
               new=AsyncMock(return_value=None)):
        with pytest.raises(ValueError, match="Email not found"):
            await authenticate_user("ghost@example.com", "any_password")