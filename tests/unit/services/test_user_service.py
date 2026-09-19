"""
Unit tests for user_service.py

All DB interactions are mocked via AsyncMock on engine.begin() / engine.connect().
Focus: business logic, branching, ValueError raises, bool guard on is_active.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.services.user_service import (
    change_user_is_active,
    check_user_role,
    list_users_filtered,
    update_own_profile,
    update_user_admin,
)

# ==========================================
# HELPERS
# ==========================================

def make_fake_user(overrides: dict = {}) -> dict:
    base = {
        "id": 1,
        "organization_id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "password_hash": "fakehash",
        "role": "STAFF",
        "is_active": True,
    }
    return {**base, **overrides}


# ==========================================
# list_users_filtered
# ==========================================

@pytest.mark.asyncio
async def test_list_users_filtered_staff_raises_value_error():
    """STAFF role must always raise ValueError — no filter bypasses it."""
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        with pytest.raises(ValueError, match="Staff members"):
            await list_users_filtered(
                organization_id=1,
                role=None,
                is_active=None,
                user_role="STAFF"
            )


@pytest.mark.asyncio
async def test_list_users_filtered_owner_adds_org_filter():
    """OWNER role must scope query to own organization_id."""
    fake_rows = [make_fake_user()]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = fake_rows

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await list_users_filtered(
            organization_id=5,
            role=None,
            is_active=None,
            user_role="OWNER"
        )

    # Verify organization_id was passed as param
    call_kwargs = mock_conn.execute.call_args
    assert "organization_id" in call_kwargs[0][1]
    assert call_kwargs[0][1]["organization_id"] == 5


@pytest.mark.asyncio
async def test_list_users_filtered_is_active_false_is_not_ignored():
    """
    Critical: `if is_active is not None` must be used — not `if is_active`.
    Passing is_active=False should still add the filter, not skip it.
    """
    fake_rows = []

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = fake_rows

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        await list_users_filtered(
            organization_id=1,
            role=None,
            is_active=False,   # <-- the critical case
            user_role="ROOT"
        )

    call_kwargs = mock_conn.execute.call_args
    assert "is_active" in call_kwargs[0][1]
    assert call_kwargs[0][1]["is_active"] == False


# ==========================================
# update_own_profile
# ==========================================

@pytest.mark.asyncio
async def test_update_own_profile_wrong_password_raises_value_error():
    from app.api.v1.services.password_service import hash_password

    hashed = hash_password("correct_password")
    fake_user = make_fake_user({"password_hash": hashed})

    with patch("app.api.v1.services.user_service.search_user_by_id",
               new=AsyncMock(return_value=fake_user)):
        with pytest.raises(ValueError, match="Current password is incorrect"):
            await update_own_profile(
                user_id=1,
                name="New Name",
                email=None,
                password=None,
                current_password="wrong_password"
            )


@pytest.mark.asyncio
async def test_update_own_profile_no_fields_returns_none():
    from app.api.v1.services.password_service import hash_password

    hashed = hash_password("correct_password")
    fake_user = make_fake_user({"password_hash": hashed})

    with patch("app.api.v1.services.user_service.search_user_by_id",
               new=AsyncMock(return_value=fake_user)):
        result = await update_own_profile(
            user_id=1,
            name=None,
            email=None,
            password=None,
            current_password="correct_password"
        )
    assert result is None


@pytest.mark.asyncio
async def test_update_own_profile_valid_update_returns_user():
    from app.api.v1.services.password_service import hash_password

    hashed = hash_password("correct_password")
    fake_user = make_fake_user({"password_hash": hashed})
    updated_user = make_fake_user({"name": "Updated Name", "password_hash": hashed})

    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.search_user_by_id",
               new=AsyncMock(side_effect=[fake_user, updated_user])):
        with patch("app.api.v1.services.user_service.engine") as mock_engine:
            mock_engine.begin.return_value = mock_conn

            result = await update_own_profile(
                user_id=1,
                name="Updated Name",
                email=None,
                password=None,
                current_password="correct_password"
            )

    assert result["name"] == "Updated Name"


# ==========================================
# update_user_admin
# ==========================================

@pytest.mark.asyncio
async def test_update_user_admin_no_fields_returns_none():
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_user_admin(
            user_id=1,
            name=None,
            email=None,
            password=None,
            role=None,
            is_active=None
        )
    assert result is None


@pytest.mark.asyncio
async def test_update_user_admin_is_active_false_is_included():
    """
    is_active=False must not be skipped by `if is_active`.
    The guard must be `if is_active is not None`.
    """
    fake_user = make_fake_user({"is_active": False})

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.search_user_by_id",
               new=AsyncMock(return_value=fake_user)):
        with patch("app.api.v1.services.user_service.engine") as mock_engine:
            mock_engine.begin.return_value = mock_conn

            result = await update_user_admin(
                user_id=1,
                name=None,
                email=None,
                password=None,
                role=None,
                is_active=False  # <-- must be included, not skipped
            )

    # Execute must have been called (UPDATE ran)
    mock_conn.execute.assert_called()


# ==========================================
# check_user_role
# ==========================================

@pytest.mark.asyncio
async def test_check_user_role_correct_role_returns_true():
    mock_result = MagicMock()
    mock_result.mappings.return_value.one_or_none.return_value = {"role": "OWNER"}

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await check_user_role(user_id=1, role="OWNER")
    assert result is True


@pytest.mark.asyncio
async def test_check_user_role_wrong_role_returns_false():
    mock_result = MagicMock()
    mock_result.mappings.return_value.one_or_none.return_value = {"role": "STAFF"}

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await check_user_role(user_id=1, role="OWNER")
    assert result is False


@pytest.mark.asyncio
async def test_check_user_role_user_not_found_returns_false():
    mock_result = MagicMock()
    mock_result.mappings.return_value.one_or_none.return_value = None

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await check_user_role(user_id=999, role="OWNER")
    assert result is False


# ==========================================
# change_user_is_active
# ==========================================

@pytest.mark.asyncio
async def test_change_user_is_active_returns_true():
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.user_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await change_user_is_active(user_id=1, is_active=False)
    assert result is True