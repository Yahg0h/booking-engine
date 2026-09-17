"""
Unit tests for availability_service.py

All helper dependencies (search_organization_by_id, search_professional_by_id, etc.)
are mocked. Focus: algorithm logic for calculating available appointment slots,
handing blackouts, existing appointments, buffer times, and error scenarios.
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.services.availability_service import (
    _timedelta_to_time,
    availability_service,
)

# ==========================================
# _timedelta_to_time
# ==========================================

def test_timedelta_to_time():
    t = time(9, 30)
    assert _timedelta_to_time(t) == time(9, 30)

    td = timedelta(hours=8, minutes=15)
    assert _timedelta_to_time(td) == time(8, 15)


# ==========================================
# availability_service error cases
# ==========================================

@pytest.mark.asyncio
async def test_availability_service_pro_does_not_offer_procedure_raises_error():
    fake_org = {"id": 1, "min_work_time": timedelta(hours=8), "max_work_time": timedelta(hours=18)}
    fake_pro = {"id": 1, "buffer_time_minutes": 10, "is_active": True}
    fake_proc = {"id": 1, "duration_minutes": 30, "is_active": True}

    with (
        patch("app.api.v1.services.availability_service.search_organization_by_id", new=AsyncMock(return_value=fake_org)),
        patch("app.api.v1.services.availability_service.search_professional_by_id", new=AsyncMock(return_value=fake_pro)),
        patch("app.api.v1.services.availability_service.search_procedure_by_id", new=AsyncMock(return_value=fake_proc)),
        patch("app.api.v1.services.availability_service.search_professional_procedure_unique", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(ValueError, match="Professional doesn't offer this procedure"):
            await availability_service(
                organization_id=1,
                professional_id=1,
                procedure_id=1,
                date=date(2026, 10, 12),  # Monday (weekday=1)
            )


@pytest.mark.asyncio
async def test_availability_service_pro_does_not_work_on_date_raises_error():
    fake_org = {"id": 1, "min_work_time": timedelta(hours=8), "max_work_time": timedelta(hours=18)}
    fake_pro = {"id": 1, "buffer_time_minutes": 10, "is_active": True}
    fake_proc = {"id": 1, "duration_minutes": 30, "is_active": True}
    fake_pp = {"organization_id": 1, "professional_id": 1, "procedure_id": 1, "is_active": True}

    # Pro only works on Tuesday (weekday=2), but target date is Monday (weekday=1)
    working_hours = [{"weekday": 2, "start_time": timedelta(hours=8), "end_time": timedelta(hours=17)}]

    with (
        patch("app.api.v1.services.availability_service.search_organization_by_id", new=AsyncMock(return_value=fake_org)),
        patch("app.api.v1.services.availability_service.search_professional_by_id", new=AsyncMock(return_value=fake_pro)),
        patch("app.api.v1.services.availability_service.search_procedure_by_id", new=AsyncMock(return_value=fake_proc)),
        patch("app.api.v1.services.availability_service.search_professional_procedure_unique", new=AsyncMock(return_value=fake_pp)),
        patch("app.api.v1.services.availability_service.list_active_working_hours_by_professional", new=AsyncMock(return_value=working_hours)),
    ):
        with pytest.raises(ValueError, match="The professional doesn't work in the selected date"):
            await availability_service(
                organization_id=1,
                professional_id=1,
                procedure_id=1,
                date=date(2026, 10, 12),  # Monday
            )


# ==========================================
# availability_service slot calculation
# ==========================================

@pytest.mark.asyncio
async def test_availability_service_returns_slots():
    """Calculates available 15-minute step slots for a clean workday."""
    target_date = date(2026, 10, 12)  # Monday
    fake_org = {"id": 1, "min_work_time": timedelta(hours=8), "max_work_time": timedelta(hours=12)}
    fake_pro = {"id": 1, "buffer_time_minutes": 0, "is_active": True}
    fake_proc = {"id": 1, "duration_minutes": 30, "is_active": True}
    fake_pp = {"organization_id": 1, "professional_id": 1, "procedure_id": 1, "is_active": True}

    working_hours = [{"weekday": 1, "start_time": timedelta(hours=8), "end_time": timedelta(hours=10)}]

    with (
        patch("app.api.v1.services.availability_service.search_organization_by_id", new=AsyncMock(return_value=fake_org)),
        patch("app.api.v1.services.availability_service.search_professional_by_id", new=AsyncMock(return_value=fake_pro)),
        patch("app.api.v1.services.availability_service.search_procedure_by_id", new=AsyncMock(return_value=fake_proc)),
        patch("app.api.v1.services.availability_service.search_professional_procedure_unique", new=AsyncMock(return_value=fake_pp)),
        patch("app.api.v1.services.availability_service.list_active_working_hours_by_professional", new=AsyncMock(return_value=working_hours)),
        patch("app.api.v1.services.availability_service.list_blackouts_by_professional", new=AsyncMock(return_value=[])),
        patch("app.api.v1.services.availability_service.list_appointments_by_time_frame", new=AsyncMock(return_value=[])),
    ):
        slots = await availability_service(
            organization_id=1,
            professional_id=1,
            procedure_id=1,
            date=target_date,
        )

    assert isinstance(slots, list)
    assert len(slots) > 0
    # First slot should be 08:00
    assert slots[0] == datetime.combine(target_date, time(8, 0))
