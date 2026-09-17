"""
Unit tests for procedure_service.py

All DB interactions are mocked via AsyncMock on engine.begin() / engine.connect().
Focus: business logic, dynamic query building (UPDATE), bool guards, access checks,
       professional-procedure relation operations.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.services.procedure_service import (
    change_pp_is_active,
    change_procedure_is_active,
    check_procedure_access,
    create_procedure,
    create_professional_procedure,
    list_procedures_by_org,
    list_professional_procedures,
    search_procedure_by_id,
    search_professional_procedure_unique,
    update_procedure,
)


# ==========================================
# HELPERS
# ==========================================

def make_fake_procedure(overrides: dict = {}) -> dict:
    base = {
        "id": 1,
        "organization_id": 10,
        "name": "Haircut",
        "description": "A standard haircut",
        "duration_minutes": 30,
        "price": Decimal("50.00"),
        "is_active": True,
    }
    return {**base, **overrides}


def make_fake_pp(overrides: dict = {}) -> dict:
    base = {
        "organization_id": 10,
        "professional_id": 1,
        "procedure_id": 1,
        "is_active": True,
    }
    return {**base, **overrides}


def _make_conn(scalar_val=None, mapping_val=None, all_val=None) -> AsyncMock:
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
# create_procedure
# ==========================================

@pytest.mark.asyncio
async def test_create_procedure_returns_new_id():
    """create_procedure must return the newly inserted procedure id."""
    mock_conn = _make_conn(scalar_val=55)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await create_procedure(
            organization_id=10,
            name="Haircut",
            description="A standard haircut",
            duration_minutes=30,
            price=Decimal("50.00"),
            is_active=True,
        )

    assert result == 55


# ==========================================
# search_procedure_by_id
# ==========================================

@pytest.mark.asyncio
async def test_search_procedure_by_id_found():
    fake_proc = make_fake_procedure()
    mock_conn = _make_conn(mapping_val=fake_proc)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_procedure_by_id(1)

    assert result == fake_proc


@pytest.mark.asyncio
async def test_search_procedure_by_id_not_found():
    mock_conn = _make_conn(mapping_val=None)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_procedure_by_id(9999)

    assert result is None


# ==========================================
# list_procedures_by_org
# ==========================================

@pytest.mark.asyncio
async def test_list_procedures_by_org_returns_list():
    rows = [make_fake_procedure(), make_fake_procedure({"id": 2, "name": "Massage"})]
    mock_conn = _make_conn(all_val=rows)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await list_procedures_by_org(organization_id=10, is_active=True)

    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_procedures_by_org_is_active_false_passes_param():
    """is_active=False must still be passed to the query — not silently skipped."""
    mock_conn = _make_conn(all_val=[])

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        await list_procedures_by_org(organization_id=10, is_active=False)

    call_params = mock_conn.execute.call_args[0][1]
    assert call_params["is_active"] is False


# ==========================================
# update_procedure
# ==========================================

@pytest.mark.asyncio
async def test_update_procedure_no_fields_returns_none():
    """All fields None -> no UPDATE should run -> returns None."""
    mock_conn = _make_conn()

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_procedure(
            id=1,
            name=None,
            description=None,
            duration_minutes=None,
            price=None,
            is_active=None,
        )

    assert result is None


@pytest.mark.asyncio
async def test_update_procedure_name_only_builds_correct_query():
    updated = make_fake_procedure({"name": "Fancy Cut"})
    mock_conn = _make_conn(mapping_val=updated)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_procedure(
            id=1,
            name="Fancy Cut",
            description=None,
            duration_minutes=None,
            price=None,
            is_active=None,
        )

    update_call_params = mock_conn.execute.call_args_list[0][0][1]
    assert "name" in update_call_params
    assert update_call_params["name"] == "Fancy Cut"


@pytest.mark.asyncio
async def test_update_procedure_is_active_false_not_skipped():
    """
    Critical: is_active=False must NOT be skipped.
    The guard in the service must be if is_active is not None, not if is_active.
    """
    updated = make_fake_procedure({"is_active": False})
    mock_conn = _make_conn(mapping_val=updated)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_procedure(
            id=1,
            name=None,
            description=None,
            duration_minutes=None,
            price=None,
            is_active=False,
        )

    update_call_params = mock_conn.execute.call_args_list[0][0][1]
    assert "is_active" in update_call_params
    assert update_call_params["is_active"] is False


@pytest.mark.asyncio
async def test_update_procedure_price_and_duration():
    """Multiple fields must all appear in the UPDATE params."""
    updated = make_fake_procedure({"price": Decimal("75.00"), "duration_minutes": 45})
    mock_conn = _make_conn(mapping_val=updated)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_procedure(
            id=1,
            name=None,
            description=None,
            duration_minutes=45,
            price=Decimal("75.00"),
            is_active=None,
        )

    update_call_params = mock_conn.execute.call_args_list[0][0][1]
    assert "price" in update_call_params
    assert "duration_minutes" in update_call_params


# ==========================================
# change_procedure_is_active
# ==========================================

@pytest.mark.asyncio
async def test_change_procedure_is_active_returns_true():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await change_procedure_is_active(id=1, is_active=False)

    assert result is True


# ==========================================
# create_professional_procedure
# ==========================================

@pytest.mark.asyncio
async def test_create_professional_procedure_returns_true():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await create_professional_procedure(
            organization_id=10,
            professional_id=1,
            procedure_id=1,
            is_active=True,
        )

    assert result is True


# ==========================================
# search_professional_procedure_unique
# ==========================================

@pytest.mark.asyncio
async def test_search_professional_procedure_unique_found():
    fake_pp = make_fake_pp()
    mock_conn = _make_conn(mapping_val=fake_pp)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_professional_procedure_unique(
            organization_id=10,
            professional_id=1,
            procedure_id=1,
            is_active=True,
        )

    assert result == fake_pp


@pytest.mark.asyncio
async def test_search_professional_procedure_unique_not_found():
    mock_conn = _make_conn(mapping_val=None)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_professional_procedure_unique(
            organization_id=10,
            professional_id=1,
            procedure_id=999,
            is_active=True,
        )

    assert result is None


# ==========================================
# list_professional_procedures
# ==========================================

@pytest.mark.asyncio
async def test_list_professional_procedures_returns_list():
    rows = [make_fake_pp(), make_fake_pp({"procedure_id": 2})]
    mock_conn = _make_conn(all_val=rows)

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await list_professional_procedures(
            organization_id=10,
            professional_id=1,
            procedure_id=None,
            is_active=True,
        )

    assert isinstance(result, list)
    assert len(result) == 2


# ==========================================
# change_pp_is_active
# ==========================================

@pytest.mark.asyncio
async def test_change_pp_is_active_returns_true():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.procedure_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await change_pp_is_active(
            organization_id=10,
            professional_id=1,
            procedure_id=1,
            is_active=False,
        )

    assert result is True


# ==========================================
# check_procedure_access
# ==========================================

@pytest.mark.asyncio
async def test_check_procedure_access_root_returns_true():
    """ROOT user must always get access."""
    with (
        patch("app.api.v1.services.procedure_service.is_root", new=AsyncMock(return_value=True)),
        patch("app.api.v1.services.procedure_service.is_owner", new=AsyncMock(return_value=False)),
    ):
        result = await check_procedure_access(user_id=1, organization_id=99)

    assert result is True


@pytest.mark.asyncio
async def test_check_procedure_access_owner_returns_true():
    """OWNER of the correct org must get access."""
    with (
        patch("app.api.v1.services.procedure_service.is_root", new=AsyncMock(return_value=False)),
        patch("app.api.v1.services.procedure_service.is_owner", new=AsyncMock(return_value=True)),
    ):
        result = await check_procedure_access(user_id=2, organization_id=10)

    assert result is True


@pytest.mark.asyncio
async def test_check_procedure_access_staff_returns_false():
    """STAFF must be denied access to procedure management."""
    with (
        patch("app.api.v1.services.procedure_service.is_root", new=AsyncMock(return_value=False)),
        patch("app.api.v1.services.procedure_service.is_owner", new=AsyncMock(return_value=False)),
    ):
        result = await check_procedure_access(user_id=3, organization_id=10)

    assert result is False
