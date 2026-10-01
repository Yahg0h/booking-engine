"""Unit tests for report_service.py using mocked SQL query results."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.api.v1.services import report_service


@pytest.mark.asyncio
async def test_generate_appointments_report_builds_summary_and_filters():
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 2, 1, tzinfo=timezone.utc)
    rows = pd.DataFrame([
        {"appointment_id": 1, "appointment_status": "COMPLETED", "procedure_price": 100.0},
        {"appointment_id": 2, "appointment_status": "CANCELLED", "procedure_price": 50.0},
        {"appointment_id": 3, "appointment_status": "NO_SHOW", "procedure_price": 75.0},
        {"appointment_id": 4, "appointment_status": "SCHEDULED", "procedure_price": 25.0},
    ])

    with patch.object(report_service.asyncio, "to_thread", new=AsyncMock(return_value=rows)) as run_query:
        result = await report_service.generate_appointments_report(
            org_id=8,
            start_date=start_date,
            end_date=end_date,
            professional_id=12,
            customer_id=15,
        )

    assert result["summary"] == {
        "total_appointments": 4,
        "completed": 1,
        "cancelled": 1,
        "no_show": 1,
        "total_revenue": 250.0,
    }
    assert result["metadata"]["organization_id"] == 8
    assert result["metadata"]["period"] == {"start_date": start_date, "end_date": end_date}
    assert result["metadata"]["filters_applied"] == {"professional_id": 12, "customer_id": 15}
    assert result["data"].equals(rows)

    query, params = run_query.await_args.args[1:3]
    assert "AND a.organization_id = :org_id" in query
    assert "AND a.professional_id = :professional_id" in query
    assert "AND a.customer_id = :customer_id" in query
    assert params == {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "org_id": 8,
        "professional_id": 12,
        "customer_id": 15,
    }


@pytest.mark.asyncio
async def test_generate_appointments_report_empty_result_uses_zero_summary():
    with patch.object(report_service.asyncio, "to_thread", new=AsyncMock(return_value=pd.DataFrame())):
        result = await report_service.generate_appointments_report()

    assert result["summary"] == {
        "total_appointments": 0,
        "completed": 0,
        "cancelled": 0,
        "no_show": 0,
        "total_revenue": 0.0,
    }
    assert result["metadata"]["organization_id"] is None
    assert result["metadata"]["period"]["end_date"] - result["metadata"]["period"]["start_date"] == timedelta(days=30)


@pytest.mark.asyncio
async def test_generate_revenue_report_separates_concrete_revenue_and_filters():
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 2, 1, tzinfo=timezone.utc)
    rows = pd.DataFrame([
        {"appointment_id": 1, "procedure_price": 125.0, "revenue_type": "Concrete"},
        {"appointment_id": 2, "procedure_price": 75.0, "revenue_type": "Estimated"},
    ])

    with patch.object(report_service.asyncio, "to_thread", new=AsyncMock(return_value=rows)) as run_query:
        result = await report_service.generate_revenue_report(
            org_id=5,
            start_date=start_date,
            end_date=end_date,
            professional_id=17,
            group_by="year",
        )

    assert result["summary"] == {
        "total_estimated_revenue": 200.0,
        "total_concrete_revenue": 125.0,
        "appointment_count": 2,
    }
    assert result["metadata"]["filters_applied"] == {"professional_id": 17, "group_by": "year"}
    query, params = run_query.await_args.args[1:3]
    assert "AND a.organization_id = :org_id" in query
    assert "AND a.professional_id = :professional_id" in query
    assert params["org_id"] == 5
    assert params["professional_id"] == 17


@pytest.mark.asyncio
async def test_generate_revenue_report_empty_result_returns_zero_summary():
    with patch.object(report_service.asyncio, "to_thread", new=AsyncMock(return_value=pd.DataFrame())):
        result = await report_service.generate_revenue_report(group_by="week")

    assert result["summary"] == {
        "total_estimated_revenue": 0.0,
        "total_concrete_revenue": 0.0,
        "appointment_count": 0,
    }
    assert result["metadata"]["period"]["end_date"] - result["metadata"]["period"]["start_date"] == timedelta(days=7)


@pytest.mark.asyncio
async def test_generate_customers_report_calculates_activity_summary_and_filters():
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 2, 1, tzinfo=timezone.utc)
    rows = pd.DataFrame([
        {"customer_id": 1, "customer_active": True, "total_appointments": 4},
        {"customer_id": 2, "customer_active": True, "total_appointments": 3},
        {"customer_id": 3, "customer_active": False, "total_appointments": 1},
    ])

    with patch.object(report_service.asyncio, "to_thread", new=AsyncMock(return_value=rows)) as run_query:
        result = await report_service.generate_customers_report(
            org_id=11,
            start_date=start_date,
            end_date=end_date,
            professional_id=21,
        )

    assert result["summary"] == {
        "total_customers": 3,
        "active_customers": 2,
        "inactive_customers": 1,
        "avg_appointments_per_customer": 2.67,
    }
    assert result["metadata"]["filters_applied"] == {"professional_id": 21}
    query, params = run_query.await_args.args[1:3]
    assert "AND a.organization_id = :org_id" in query
    assert "AND a.professional_id = :professional_id" in query
    assert "WHERE c.organization_id = :org_id" in query
    assert params["org_id"] == 11
    assert params["professional_id"] == 21


@pytest.mark.asyncio
async def test_generate_customers_report_empty_result_uses_zero_summary():
    with patch.object(report_service.asyncio, "to_thread", new=AsyncMock(return_value=pd.DataFrame())):
        result = await report_service.generate_customers_report()

    assert result["summary"] == {
        "total_customers": 0,
        "active_customers": 0,
        "inactive_customers": 0,
        "avg_appointments_per_customer": 0.0,
    }
    assert result["metadata"]["period"]["end_date"] - result["metadata"]["period"]["start_date"] == timedelta(days=30)
