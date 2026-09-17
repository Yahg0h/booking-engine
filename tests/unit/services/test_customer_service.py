"""
Unit tests for customer_service.py

All DB interactions are mocked via AsyncMock on engine.begin() / engine.connect().
Focus: business logic, dynamic query building (UPDATE / filters), bool guards, access checks.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.services.customer_service import (
    change_customer_is_active,
    check_customer_access,
    create_customer,
    list_customers_filtered,
    search_customer_by_id,
    update_customer_last_appointment,
    update_customers,
)

# ==========================================
# HELPERS
# ==========================================

def make_fake_customer(overrides: dict = {}) -> dict:
    base = {
        "id": 1,
        "organization_id": 10,
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1234567890",
        "last_appointment_at": None,
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
# create_customer
# ==========================================

@pytest.mark.asyncio
async def test_create_customer_returns_id():
    mock_conn = _make_conn(scalar_val=15)

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await create_customer(
            organization_id=10,
            name="Jane Doe",
            email="jane@example.com",
            phone="+1234567890",
            is_active=True,
        )

    assert result == 15


# ==========================================
# search_customer_by_id
# ==========================================

@pytest.mark.asyncio
async def test_search_customer_by_id_found():
    fake_cust = make_fake_customer()
    mock_conn = _make_conn(mapping_val=fake_cust)

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_customer_by_id(1)

    assert result == fake_cust


@pytest.mark.asyncio
async def test_search_customer_by_id_not_found():
    mock_conn = _make_conn(mapping_val=None)

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_customer_by_id(9999)

    assert result is None


# ==========================================
# list_customers_filtered
# ==========================================

@pytest.mark.asyncio
async def test_list_customers_filtered_returns_list():
    rows = [make_fake_customer(), make_fake_customer({"id": 2, "name": "John"})]
    mock_conn = _make_conn(all_val=rows)

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await list_customers_filtered(
            organization_id=10,
            email=None,
            phone=None,
            last_appointment_at=None,
            is_active=True,
        )

    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_customers_filtered_is_active_false_passes_param():
    """is_active=False must still be passed to query params."""
    mock_conn = _make_conn(all_val=[])

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        await list_customers_filtered(
            organization_id=10,
            email=None,
            phone=None,
            last_appointment_at=None,
            is_active=False,
        )

    call_params = mock_conn.execute.call_args[0][1]
    assert call_params["is_active"] is False


# ==========================================
# update_customers
# ==========================================

@pytest.mark.asyncio
async def test_update_customers_no_fields_returns_none():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_customers(
            id=1,
            name=None,
            email=None,
            phone=None,
            is_active=None,
        )

    assert result is None


@pytest.mark.asyncio
async def test_update_customers_is_active_false_not_skipped():
    """is_active=False must not be skipped by if is_active."""
    updated = make_fake_customer({"is_active": False})
    mock_conn = _make_conn(mapping_val=updated)

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        await update_customers(
            id=1,
            name=None,
            email=None,
            phone=None,
            is_active=False,
        )

    update_params = mock_conn.execute.call_args_list[0][0][1]
    assert "is_active" in update_params
    assert update_params["is_active"] is False


# ==========================================
# change_customer_is_active
# ==========================================

@pytest.mark.asyncio
async def test_change_customer_is_active_returns_true():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await change_customer_is_active(id=1, is_active=False)

    assert result is True


# ==========================================
# update_customer_last_appointment
# ==========================================

@pytest.mark.asyncio
async def test_update_customer_last_appointment_returns_true():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.customer_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_customer_last_appointment(
            customer_id=1,
            last_appointment_at=datetime.now(),
        )

    assert result is True


# ==========================================
# check_customer_access
# ==========================================

@pytest.mark.asyncio
async def test_check_customer_access_root_returns_true():
    fake_user = {"id": 1, "organization_id": None, "role": "ROOT"}

    with (
        patch("app.api.v1.services.customer_service.search_user_by_id", new=AsyncMock(return_value=fake_user)),
        patch("app.api.v1.services.customer_service.search_professional_by_user_id", new=AsyncMock(return_value=None)),
    ):
        result = await check_customer_access(user_id=1, organization_id=10, allow_staff=True)

    assert result is True


@pytest.mark.asyncio
async def test_check_customer_access_owner_same_org_returns_true():
    fake_user = {"id": 2, "organization_id": 10, "role": "OWNER"}

    with (
        patch("app.api.v1.services.customer_service.search_user_by_id", new=AsyncMock(return_value=fake_user)),
        patch("app.api.v1.services.customer_service.search_professional_by_user_id", new=AsyncMock(return_value=None)),
    ):
        result = await check_customer_access(user_id=2, organization_id=10, allow_staff=True)

    assert result is True


@pytest.mark.asyncio
async def test_check_customer_access_staff_allow_staff_true_returns_true():
    fake_user = {"id": 3, "organization_id": 10, "role": "STAFF"}
    fake_pro = {"id": 1, "organization_id": 10, "user_id": 3}

    with (
        patch("app.api.v1.services.customer_service.search_user_by_id", new=AsyncMock(return_value=fake_user)),
        patch("app.api.v1.services.customer_service.search_professional_by_user_id", new=AsyncMock(return_value=fake_pro)),
    ):
        result = await check_customer_access(user_id=3, organization_id=10, allow_staff=True)

    assert result is True


@pytest.mark.asyncio
async def test_check_customer_access_staff_allow_staff_false_returns_false():
    fake_user = {"id": 3, "organization_id": 10, "role": "STAFF"}
    fake_pro = {"id": 1, "organization_id": 10, "user_id": 3}

    with (
        patch("app.api.v1.services.customer_service.search_user_by_id", new=AsyncMock(return_value=fake_user)),
        patch("app.api.v1.services.customer_service.search_professional_by_user_id", new=AsyncMock(return_value=fake_pro)),
    ):
        result = await check_customer_access(user_id=3, organization_id=10, allow_staff=False)

    assert result is False
