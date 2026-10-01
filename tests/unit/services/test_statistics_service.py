"""
Unit tests for statistics_service.py.

Database reads are mocked through asyncio.to_thread so the calculations and
query parameters can be tested without opening a database connection.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.api.v1.services import statistics_service

# ==========================================
# get_appointments_statistics
# ==========================================

@pytest.mark.asyncio
async def test_get_appointments_statistics_calculates_rates_and_scopes_query():
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 1, 31, tzinfo=timezone.utc)
    rows = pd.DataFrame([{"total": 8, "cancelled": 2, "no_show": 1}])

    with patch.object(statistics_service.asyncio, "to_thread", new=AsyncMock(return_value=rows)) as run_query:
        result = await statistics_service.get_appointments_statistics(12, start_date, end_date)

    assert result == {
        "total": 8,
        "cancelled": 2,
        "no_show": 1,
        "tax_cancelled": 25.0,
        "tax_no_show": 12.5,
        "period": {"start_date": start_date, "end_date": end_date},
    }
    query, params = run_query.await_args.args[1:]
    assert "AND organization_id = :org_id" in query
    assert params == {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "org_id": 12,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [pd.DataFrame(), pd.DataFrame([{"total": 0, "cancelled": 0, "no_show": 0}])])
async def test_get_appointments_statistics_returns_zero_rates_when_empty(rows):
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 1, 31, tzinfo=timezone.utc)

    with patch.object(statistics_service.asyncio, "to_thread", new=AsyncMock(return_value=rows)):
        result = await statistics_service.get_appointments_statistics(None, start_date, end_date)

    assert result["total"] == 0
    assert result["cancelled"] == 0
    assert result["no_show"] == 0
    assert result["tax_cancelled"] == 0.0
    assert result["tax_no_show"] == 0.0
    assert result["period"] == {"start_date": start_date, "end_date": end_date}


@pytest.mark.asyncio
async def test_get_appointments_statistics_global_query_omits_organization_filter():
    rows = pd.DataFrame([{"total": 1, "cancelled": 0, "no_show": 0}])

    with patch.object(statistics_service.asyncio, "to_thread", new=AsyncMock(return_value=rows)) as run_query:
        await statistics_service.get_appointments_statistics(None)

    query, params = run_query.await_args.args[1:]
    assert "organization_id = :org_id" not in query
    assert set(params) == {"start_date", "end_date"}


# ==========================================
# get_revenue_statistics
# ==========================================

@pytest.mark.asyncio
async def test_get_revenue_statistics_separates_estimated_and_concrete_revenue():
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=30)
    end_date = now + timedelta(days=30)
    rows = pd.DataFrame([
        {"id": 1, "start_at": now - timedelta(days=20), "status": "COMPLETED", "price": 100.0},
        {"id": 2, "start_at": now + timedelta(days=20), "status": "SCHEDULED", "price": 50.0},
    ])

    with patch.object(statistics_service.asyncio, "to_thread", new=AsyncMock(return_value=rows)) as run_query:
        result = await statistics_service.get_revenue_statistics(7, start_date, end_date, "week")

    assert sum(result["estimated"].values()) == 150.0
    assert sum(result["concrete"].values()) == 100.0
    assert result["period"] == {
        "start_date": start_date,
        "end_date": end_date,
        "group_by": "week",
    }
    query, params = run_query.await_args.args[1:]
    assert "AND a.organization_id = :org_id" in query
    assert params["org_id"] == 7


@pytest.mark.asyncio
async def test_get_revenue_statistics_empty_result_returns_empty_groups():
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 2, 1, tzinfo=timezone.utc)

    with patch.object(statistics_service.asyncio, "to_thread", new=AsyncMock(return_value=pd.DataFrame())):
        result = await statistics_service.get_revenue_statistics(None, start_date, end_date)

    assert result == {
        "estimated": {},
        "concrete": {},
        "period": {"start_date": start_date, "end_date": end_date, "group_by": "week"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("group_by", "expected_days"),
    [("week", 7), ("month", 30), ("year", 365), ("invalid", 30)],
)
async def test_get_revenue_statistics_default_period_depends_on_grouping(group_by, expected_days):
    end_date = datetime(2025, 4, 15, tzinfo=timezone.utc)

    with patch.object(statistics_service.asyncio, "to_thread", new=AsyncMock(return_value=pd.DataFrame())):
        result = await statistics_service.get_revenue_statistics(
            None,
            end_date=end_date,
            group_by=group_by,
        )

    assert result["period"]["start_date"] == end_date - timedelta(days=expected_days)
    assert result["period"]["end_date"] == end_date
    assert result["period"]["group_by"] == group_by


# ==========================================
# get_customers_statistics
# ==========================================

@pytest.mark.asyncio
async def test_get_customers_statistics_calculates_engagement_and_professional_counts():
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 1, 31, tzinfo=timezone.utc)
    professional_rows = pd.DataFrame([
        {"professional_id": 3, "professional_name": "Dr. A", "unique_customers": 4},
        {"professional_id": 9, "professional_name": "Dr. B", "unique_customers": 2},
    ])
    customer_rows = pd.DataFrame([{"engaged_count": 6, "inactive_count": 4, "total_count": 10}])

    with patch.object(
        statistics_service.asyncio,
        "to_thread",
        new=AsyncMock(side_effect=[professional_rows, customer_rows]),
    ) as run_query:
        result = await statistics_service.get_customers_statistics(15, start_date, end_date)

    assert result == {
        "unique_per_professional": {"prof_3": 4, "prof_9": 2},
        "engaged": 6,
        "inactive": 4,
        "tax_engaged": 60.0,
        "period": {"start_date": start_date, "end_date": end_date},
    }
    assert run_query.await_count == 2
    first_query, first_params = run_query.await_args_list[0].args[1:]
    second_query, second_params = run_query.await_args_list[1].args[1:]
    assert "a.organization_id = :org_id" in first_query
    assert "WHERE p.organization_id = :org_id" in first_query
    assert "WHERE organization_id = :org_id" in second_query
    assert first_params == second_params == {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "org_id": 15,
    }


@pytest.mark.asyncio
async def test_get_customers_statistics_zeroes_empty_query_results():
    with patch.object(
        statistics_service.asyncio,
        "to_thread",
        new=AsyncMock(side_effect=[pd.DataFrame(), pd.DataFrame()]),
    ):
        result = await statistics_service.get_customers_statistics(None)

    assert result["unique_per_professional"] == {}
    assert result["engaged"] == 0
    assert result["inactive"] == 0
    assert result["tax_engaged"] == 0.0


# ==========================================
# Global wrapper functions
# ==========================================

@pytest.mark.asyncio
async def test_global_statistics_wrappers_forward_arguments():
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 2, 1, tzinfo=timezone.utc)

    with (
        patch.object(statistics_service, "get_appointments_statistics", new=AsyncMock(return_value={"kind": "appointments"})) as appointments,
        patch.object(statistics_service, "get_revenue_statistics", new=AsyncMock(return_value={"kind": "revenue"})) as revenue,
        patch.object(statistics_service, "get_customers_statistics", new=AsyncMock(return_value={"kind": "customers"})) as customers,
    ):
        appointment_result = await statistics_service.get_appointments_statistics_global(start_date, end_date)
        revenue_result = await statistics_service.get_revenue_statistics_global(start_date, end_date, "month")
        customer_result = await statistics_service.get_customers_statistics_global(start_date, end_date)

    assert appointment_result == {"kind": "appointments"}
    assert revenue_result == {"kind": "revenue"}
    assert customer_result == {"kind": "customers"}
    appointments.assert_awaited_once_with(org_id=None, start_date=start_date, end_date=end_date)
    revenue.assert_awaited_once_with(
        org_id=None,
        start_date=start_date,
        end_date=end_date,
        group_by="month",
    )
    customers.assert_awaited_once_with(org_id=None, start_date=start_date, end_date=end_date)
