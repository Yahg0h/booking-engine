"""
Unit tests for professional_service.py

All DB interactions are mocked via AsyncMock on engine.begin() / engine.connect().
Focus: business logic, dynamic query building (UPDATE), bool guards, access checks.
"""

from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.services.professional_service import (
    change_buffer_time,
    change_is_active,
    check_existing_weekday,
    check_professional_access,
    create_professionals,
    create_working_hours,
    list_all_professionals,
    list_professionals_by_org,
    search_professional_by_id,
    search_professional_by_user_id,
    update_professional,
    update_working_hours,
)


# ==========================================
# HELPERS
# ==========================================

def make_fake_professional(overrides: dict = {}) -> dict:
    base = {
        "id": 1,
        "organization_id": 10,
        "user_id": 5,
        "name": "Dr. Test",
        "buffer_time_minutes": 15,
        "is_active": True,
    }
    return {**base, **overrides}


def make_fake_working_hour(overrides: dict = {}) -> dict:
    base = {
        "id": 1,
        "professional_id": 1,
        "weekday": 1,
        "start_time": time(8, 0),
        "end_time": time(17, 0),
        "is_active": True,
    }
    return {**base, **overrides}


def _make_conn(scalar_val=None, mapping_val=None, all_val=None) -> AsyncMock:
    """Build a mock async connection context manager."""
    mock_result = MagicMock()
    mock_result.scalar.return_value = scalar_val
    mock_result.mappings.return_value.one_or_none.return_value = mapping_val
    mock_result.mappings.return_value.all.return_value = all_val or []

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    return mock_conn


# ==========================================
# create_professionals
# ==========================================

@pytest.mark.asyncio
async def test_create_professionals_returns_new_id():
    """create_professionals must return the newly inserted professional id."""
    mock_conn = _make_conn(scalar_val=42)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await create_professionals(
            organization_id=10,
            user_id=5,
            name="Dr. Test",
            buffer_time_minutes=15,
            is_active=True,
        )

    assert result == 42


# ==========================================
# search_professional_by_id
# ==========================================

@pytest.mark.asyncio
async def test_search_professional_by_id_found():
    fake_pro = make_fake_professional()
    mock_conn = _make_conn(mapping_val=fake_pro)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_professional_by_id(1)

    assert result == fake_pro


@pytest.mark.asyncio
async def test_search_professional_by_id_not_found():
    mock_conn = _make_conn(mapping_val=None)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_professional_by_id(9999)

    assert result is None


# ==========================================
# search_professional_by_user_id
# ==========================================

@pytest.mark.asyncio
async def test_search_professional_by_user_id_found():
    fake_pro = make_fake_professional({"user_id": 7})
    mock_conn = _make_conn(mapping_val=fake_pro)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_professional_by_user_id(7)

    assert result["user_id"] == 7


# ==========================================
# list_professionals_by_org
# ==========================================

@pytest.mark.asyncio
async def test_list_professionals_by_org_returns_list():
    rows = [make_fake_professional(), make_fake_professional({"id": 2, "name": "Dr. B"})]
    mock_conn = _make_conn(all_val=rows)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await list_professionals_by_org(organization_id=10, is_active=True)

    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_professionals_by_org_is_active_false_passes_param():
    """is_active=False must still be passed to the query — not silently skipped."""
    mock_conn = _make_conn(all_val=[])

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        await list_professionals_by_org(organization_id=10, is_active=False)

    call_params = mock_conn.execute.call_args[0][1]
    assert call_params["is_active"] is False


# ==========================================
# list_all_professionals
# ==========================================

@pytest.mark.asyncio
async def test_list_all_professionals_returns_list():
    rows = [make_fake_professional()]
    mock_conn = _make_conn(all_val=rows)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await list_all_professionals(is_active=True)

    assert isinstance(result, list)
    assert len(result) == 1


# ==========================================
# update_professional
# ==========================================

@pytest.mark.asyncio
async def test_update_professional_no_fields_returns_none():
    """All fields None -> no UPDATE should run -> returns None."""
    mock_conn = _make_conn()

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_professional(
            id=1,
            organization_id=None,
            name=None,
            user_id=None,
            buffer_time_minutes=None,
            is_active=None,
        )

    assert result is None


@pytest.mark.asyncio
async def test_update_professional_name_only_builds_correct_query():
    """Updating only name must include 'name' param in the SQL execute call."""
    updated = make_fake_professional({"name": "Dr. Updated"})
    mock_conn = _make_conn(mapping_val=updated)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_professional(
            id=1,
            organization_id=None,
            name="Dr. Updated",
            user_id=None,
            buffer_time_minutes=None,
            is_active=None,
        )

    # First call is the UPDATE — verify 'name' is in the params
    update_call_params = mock_conn.execute.call_args_list[0][0][1]
    assert "name" in update_call_params
    assert update_call_params["name"] == "Dr. Updated"


@pytest.mark.asyncio
async def test_update_professional_is_active_false_not_skipped():
    """
    Critical: is_active=False must NOT be skipped.
    The guard in the service must be `if is_active is not None`, not `if is_active`.
    """
    updated = make_fake_professional({"is_active": False})
    mock_conn = _make_conn(mapping_val=updated)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_professional(
            id=1,
            organization_id=None,
            name=None,
            user_id=None,
            buffer_time_minutes=None,
            is_active=False,
        )

    update_call_params = mock_conn.execute.call_args_list[0][0][1]
    assert "is_active" in update_call_params
    assert update_call_params["is_active"] is False


@pytest.mark.asyncio
async def test_update_professional_multiple_fields():
    """Multiple fields must all appear in the UPDATE params."""
    updated = make_fake_professional({"name": "Dr. Multi", "buffer_time_minutes": 30})
    mock_conn = _make_conn(mapping_val=updated)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_professional(
            id=1,
            organization_id=None,
            name="Dr. Multi",
            user_id=None,
            buffer_time_minutes=30,
            is_active=None,
        )

    update_call_params = mock_conn.execute.call_args_list[0][0][1]
    assert "name" in update_call_params
    assert "buffer_time_minutes" in update_call_params


# ==========================================
# change_is_active
# ==========================================

@pytest.mark.asyncio
async def test_change_is_active_returns_true():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await change_is_active(id=1, is_active=False)

    assert result is True


# ==========================================
# create_working_hours
# ==========================================

@pytest.mark.asyncio
async def test_create_working_hours_returns_id():
    mock_conn = _make_conn(scalar_val=99)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await create_working_hours(
            professional_id=1,
            weekday=1,
            start_time=time(8, 0),
            end_time=time(17, 0),
            is_active=True,
        )

    assert result == 99


# ==========================================
# update_working_hours
# ==========================================

@pytest.mark.asyncio
async def test_update_working_hours_no_fields_returns_none():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_working_hours(
            id=1,
            weekday=None,
            start_time=None,
            end_time=None,
            is_active=None,
        )

    assert result is None


@pytest.mark.asyncio
async def test_update_working_hours_is_active_false_not_skipped():
    """is_active=False in working hours update must not be ignored."""
    updated_wk = make_fake_working_hour({"is_active": False})
    mock_conn = _make_conn(mapping_val=updated_wk)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_working_hours(
            id=1,
            weekday=None,
            start_time=None,
            end_time=None,
            is_active=False,
        )

    update_params = mock_conn.execute.call_args_list[0][0][1]
    assert "is_active" in update_params
    assert update_params["is_active"] is False


@pytest.mark.asyncio
async def test_update_working_hours_weekday_included_in_params():
    updated_wk = make_fake_working_hour({"weekday": 3})
    mock_conn = _make_conn(mapping_val=updated_wk)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_working_hours(
            id=1,
            weekday=3,
            start_time=None,
            end_time=None,
            is_active=None,
        )

    update_params = mock_conn.execute.call_args_list[0][0][1]
    assert "weekday" in update_params
    assert update_params["weekday"] == 3


# ==========================================
# check_existing_weekday
# ==========================================

@pytest.mark.asyncio
async def test_check_existing_weekday_exists_returns_true():
    mock_conn = _make_conn(mapping_val={"id": 1, "weekday": 2})

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await check_existing_weekday(weekday=2, professional_id=1)

    assert result is True


@pytest.mark.asyncio
async def test_check_existing_weekday_not_exists_returns_false():
    mock_conn = _make_conn(mapping_val=None)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await check_existing_weekday(weekday=5, professional_id=1)

    assert result is False


# ==========================================
# change_buffer_time
# ==========================================

@pytest.mark.asyncio
async def test_change_buffer_time_returns_updated_row():
    updated = make_fake_professional({"buffer_time_minutes": 30})
    mock_conn = _make_conn(mapping_val=updated)

    with patch("app.api.v1.services.professional_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await change_buffer_time(id=1, buffer_time_minutes=30)

    assert result["buffer_time_minutes"] == 30


# ==========================================
# check_professional_access
# ==========================================

@pytest.mark.asyncio
async def test_check_professional_access_root_returns_true():
    """ROOT user must always get access regardless of organization."""
    with (
        patch("app.api.v1.services.professional_service.is_root", new=AsyncMock(return_value=True)),
        patch("app.api.v1.services.professional_service.is_owner", new=AsyncMock(return_value=False)),
    ):
        result = await check_professional_access(user_id=1, organization_id=99)

    assert result is True


@pytest.mark.asyncio
async def test_check_professional_access_owner_returns_true():
    """OWNER of the correct org must get access."""
    with (
        patch("app.api.v1.services.professional_service.is_root", new=AsyncMock(return_value=False)),
        patch("app.api.v1.services.professional_service.is_owner", new=AsyncMock(return_value=True)),
    ):
        result = await check_professional_access(user_id=2, organization_id=10)

    assert result is True


@pytest.mark.asyncio
async def test_check_professional_access_staff_returns_false():
    """STAFF (neither root nor owner) must be denied."""
    with (
        patch("app.api.v1.services.professional_service.is_root", new=AsyncMock(return_value=False)),
        patch("app.api.v1.services.professional_service.is_owner", new=AsyncMock(return_value=False)),
    ):
        result = await check_professional_access(user_id=3, organization_id=10)

    assert result is False
