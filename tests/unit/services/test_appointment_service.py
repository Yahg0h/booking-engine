"""
Unit tests for appointment_service.py

All DB interactions are mocked via AsyncMock on engine.begin() / engine.connect().
Focus: distributed locks, availability checks, dynamic query building, access checks.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.services.appointment_service import (
    appointment_canceled,
    appointment_completed,
    check_appointment_access,
    create_appointment,
    list_appointments_by_time_frame,
    list_appointments_filtered,
    search_appointment_by_id,
    update_appointments,
)

# ==========================================
# HELPERS
# ==========================================

def make_fake_appointment(overrides: dict = {}) -> dict:
    now = datetime.now()
    base = {
        "id": 1,
        "organization_id": 10,
        "customer_id": 1,
        "professional_id": 1,
        "procedure_id": 1,
        "start_at": now,
        "end_at": now + timedelta(minutes=30),
        "status": "SCHEDULED",
        "notes": "Initial appointment",
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
# create_appointment
# ==========================================

@pytest.mark.asyncio
async def test_create_appointment_lock_failed_raises_value_error():
    """If distributed lock cannot be acquired, raise ValueError."""
    now = datetime.now()

    with patch("app.api.v1.services.appointment_service.acquire_lock", return_value=False):
        with patch("app.api.v1.services.appointment_service.engine"):
            with pytest.raises(ValueError, match="Slot no longer available"):
                await create_appointment(
                    organization_id=10,
                    customer_id=1,
                    professional_id=1,
                    procedure_id=1,
                    start_at=now,
                    status="SCHEDULED",
                )


@pytest.mark.asyncio
async def test_create_appointment_slot_unavailable_raises_value_error():
    """If requested start_at is not in available_slots, raise ValueError."""
    now = datetime.now()

    with (
        patch("app.api.v1.services.appointment_service.acquire_lock", return_value=True),
        patch("app.api.v1.services.appointment_service.release_lock"),
        patch("app.api.v1.services.availability_service.availability_service", new=AsyncMock(return_value=[])),
    ):
        with patch("app.api.v1.services.appointment_service.engine"):
            with pytest.raises(ValueError, match="Selected time is not available"):
                await create_appointment(
                    organization_id=10,
                    customer_id=1,
                    professional_id=1,
                    procedure_id=1,
                    start_at=now,
                    status="SCHEDULED",
                )


@pytest.mark.asyncio
async def test_create_appointment_success():
    """When lock is acquired and slot is available, appointment is created."""
    now = datetime.now()
    fake_procedure = {"id": 1, "duration_minutes": 30}
    mock_conn = _make_conn(scalar_val=77)

    with (
        patch("app.api.v1.services.appointment_service.acquire_lock", return_value=True),
        patch("app.api.v1.services.appointment_service.release_lock"),
        patch("app.api.v1.services.availability_service.availability_service", new=AsyncMock(return_value=[now])),
        patch("app.api.v1.services.appointment_service.search_procedure_by_id", new=AsyncMock(return_value=fake_procedure)),
    ):
        with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
            mock_engine.begin.return_value = mock_conn

            result = await create_appointment(
                organization_id=10,
                customer_id=1,
                professional_id=1,
                procedure_id=1,
                start_at=now,
                status="SCHEDULED",
            )

    assert result == 77


# ==========================================
# search_appointment_by_id
# ==========================================

@pytest.mark.asyncio
async def test_search_appointment_by_id_found():
    fake_app = make_fake_appointment()
    mock_conn = _make_conn(mapping_val=fake_app)

    with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_appointment_by_id(1)

    assert result == fake_app


@pytest.mark.asyncio
async def test_search_appointment_by_id_not_found():
    mock_conn = _make_conn(mapping_val=None)

    with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await search_appointment_by_id(9999)

    assert result is None


# ==========================================
# list_appointments_filtered
# ==========================================

@pytest.mark.asyncio
async def test_list_appointments_filtered_returns_list():
    rows = [make_fake_appointment()]
    mock_conn = _make_conn(all_val=rows)

    with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await list_appointments_filtered(
            organization_id=10,
            customer_id=None,
            professional_id=None,
            procedure_id=None,
            start_at=None,
            end_at=None,
            status=None,
        )

    assert isinstance(result, list)
    assert len(result) == 1


# ==========================================
# list_appointments_by_time_frame
# ==========================================

@pytest.mark.asyncio
async def test_list_appointments_by_time_frame_returns_list():
    now = datetime.now()
    rows = [{"id": 1, "start_at": now, "end_at": now + timedelta(minutes=30)}]
    mock_conn = _make_conn(all_val=rows)

    with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await list_appointments_by_time_frame(
            organization_id=10,
            professional_id=1,
            start_at=now,
            end_at=now + timedelta(days=1),
        )

    assert isinstance(result, list)
    assert len(result) == 1


# ==========================================
# update_appointments
# ==========================================

@pytest.mark.asyncio
async def test_update_appointments_no_fields_returns_none():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_appointments(
            id=1,
            organization_id=10,
            customer_id=1,
            professional_id=1,
            procedure_id=1,
            start_at=None,
            end_at=None,
            status=None,
            notes=None,
        )

    assert result is None


@pytest.mark.asyncio
async def test_update_appointments_status_only_success():
    fake_app = make_fake_appointment({"status": "COMPLETED"})
    mock_conn = _make_conn(mapping_val=fake_app)

    with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_appointments(
            id=1,
            organization_id=10,
            customer_id=1,
            professional_id=1,
            procedure_id=1,
            start_at=None,
            end_at=None,
            status="COMPLETED",
            notes=None,
        )

    assert result["status"] == "COMPLETED"


# ==========================================
# appointment_completed / appointment_canceled
# ==========================================

@pytest.mark.asyncio
async def test_appointment_completed_returns_true():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await appointment_completed(1)

    assert result is True


@pytest.mark.asyncio
async def test_appointment_canceled_returns_true():
    mock_conn = _make_conn()

    with patch("app.api.v1.services.appointment_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await appointment_canceled(1)

    assert result is True


# ==========================================
# check_appointment_access
# ==========================================

@pytest.mark.asyncio
async def test_check_appointment_access_root_returns_true():
    fake_user = {"id": 1, "organization_id": None, "role": "ROOT"}

    with (
        patch("app.api.v1.services.appointment_service.search_user_by_id", new=AsyncMock(return_value=fake_user)),
        patch("app.api.v1.services.appointment_service.search_professional_by_user_id", new=AsyncMock(return_value=None)),
    ):
        result = await check_appointment_access(user_id=1, organization_id=10)

    assert result is True


@pytest.mark.asyncio
async def test_check_appointment_access_owner_same_org_returns_true():
    fake_user = {"id": 2, "organization_id": 10, "role": "OWNER"}

    with (
        patch("app.api.v1.services.appointment_service.search_user_by_id", new=AsyncMock(return_value=fake_user)),
        patch("app.api.v1.services.appointment_service.search_professional_by_user_id", new=AsyncMock(return_value=None)),
    ):
        result = await check_appointment_access(user_id=2, organization_id=10)

    assert result is True
