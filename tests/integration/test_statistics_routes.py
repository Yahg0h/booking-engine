"""Integration tests for organization and root statistics routes."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.v1.routes import organizations as organizations_route
from app.api.v1.routes.root import statistics as root_statistics_route
from app.api.v1.services import cache_service
from app.api.v1.services.auth_service import verify_user_token
from app.main import app

START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2025, 2, 1, tzinfo=timezone.utc)


@pytest.fixture
def authenticated_headers(monkeypatch):
    async def return_test_user():
        return 17

    monkeypatch.setitem(app.dependency_overrides, verify_user_token, return_test_user)
    return {"Authorization": "Bearer integration-test-token"}


def _statistics_result(kind: str) -> dict:
    period = {"start_date": START_DATE, "end_date": END_DATE}

    if kind == "appointments":
        return {
            "total": 4,
            "cancelled": 1,
            "no_show": 0,
            "tax_cancelled": 25.0,
            "tax_no_show": 0.0,
            "period": period,
        }
    if kind == "revenue":
        return {
            "estimated": {"2025-01-05": 200.0},
            "concrete": {"2025-01-05": 100.0},
            "period": {**period, "group_by": "week"},
        }
    return {
        "unique_per_professional": {"prof_2": 3},
        "engaged": 3,
        "inactive": 1,
        "tax_engaged": 75.0,
        "period": period,
    }


def _mock_cache_miss(monkeypatch):
    get_cached = Mock(return_value=None)
    set_cached = Mock()
    monkeypatch.setattr(cache_service, "get_cached", get_cached)
    monkeypatch.setattr(cache_service, "set_cached", set_cached)
    return get_cached, set_cached


def _assert_cached_result(get_cached, set_cached, route_name: str, stats: dict, ttl: int):
    get_cached.assert_called_once()
    cache_key = get_cached.call_args.args[0]
    assert cache_key.startswith(f"cache:{route_name}:")
    assert "'user_id': 17" in cache_key
    set_cached.assert_called_once_with(cache_key, stats, ttl)


# ==========================================
# Root statistics routes
# ==========================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "path", "service_name", "route_name", "ttl", "service_args"),
    [
        (
            "appointments",
            "/v1/root/statistics/appointments/global",
            "get_appointments_statistics_global",
            "all_appointment_statistics",
            300,
            (None, None),
        ),
        (
            "revenue",
            "/v1/root/statistics/revenue/global",
            "get_revenue_statistics_global",
            "all_revenue_statistics",
            600,
            (None, None, "week"),
        ),
        (
            "customers",
            "/v1/root/statistics/customers/global",
            "get_customers_statistics_global",
            "all_customer_statistics",
            900,
            (None, None),
        ),
    ],
)
async def test_root_global_statistics_routes_return_and_cache_results(
    client, monkeypatch, authenticated_headers, kind, path, service_name, route_name, ttl, service_args
):
    stats = _statistics_result(kind)
    service_mock = AsyncMock(return_value=stats)
    get_cached, set_cached = _mock_cache_miss(monkeypatch)
    monkeypatch.setattr(root_statistics_route, service_name, service_mock)
    monkeypatch.setattr(root_statistics_route, "is_root", AsyncMock(return_value=True))

    response = await client.get(path, headers=authenticated_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["period"]["start_date"] == START_DATE.isoformat()
    assert body["period"]["end_date"] == END_DATE.isoformat()
    service_mock.assert_awaited_once_with(*service_args)
    _assert_cached_result(get_cached, set_cached, route_name, stats, ttl)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "path_suffix", "service_name", "route_name", "ttl", "service_args"),
    [
        ("appointments", "appointments", "get_appointments_statistics", "appointment_statistics", 300, (None, None, None)),
        ("revenue", "revenue", "get_revenue_statistics", "revenue_statistics", 600, (None, None, None, "week")),
        ("customers", "customers", "get_customers_statistics", "customer_statistics", 900, (None, None, None)),
    ],
)
async def test_root_organization_statistics_routes_return_and_cache_results(
    client, monkeypatch, authenticated_headers, kind, path_suffix, service_name, route_name, ttl, service_args
):
    organization_id = 321
    stats = _statistics_result(kind)
    service_mock = AsyncMock(return_value=stats)
    get_cached, set_cached = _mock_cache_miss(monkeypatch)
    monkeypatch.setattr(root_statistics_route, service_name, service_mock)
    monkeypatch.setattr(
        root_statistics_route,
        "search_organization_by_id",
        AsyncMock(return_value={"id": organization_id}),
    )
    monkeypatch.setattr(root_statistics_route, "is_root", AsyncMock(return_value=True))

    response = await client.get(
        f"/v1/root/statistics/{path_suffix}/{organization_id}",
        headers=authenticated_headers,
    )

    assert response.status_code == 200
    assert response.json()["period"]["start_date"] == START_DATE.isoformat()
    service_mock.assert_awaited_once_with(organization_id, *service_args[1:])
    _assert_cached_result(get_cached, set_cached, route_name, stats, ttl)


# ==========================================
# Organization statistics routes
# ==========================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "path_suffix", "service_name", "route_name", "ttl", "service_args"),
    [
        ("appointments", "appointments", "get_appointments_statistics", "appointment_statistics", 300, (None, None)),
        ("revenue", "revenue", "get_revenue_statistics", "revenue_statistics", 600, (None, None, "week")),
        ("customers", "customers", "get_customers_statistics", "customer_statistics", 900, (None, None)),
    ],
)
async def test_organization_statistics_routes_return_and_cache_results(
    client, monkeypatch, authenticated_headers, kind, path_suffix, service_name, route_name, ttl, service_args
):
    organization_id = 654
    stats = _statistics_result(kind)
    service_mock = AsyncMock(return_value=stats)
    get_cached, set_cached = _mock_cache_miss(monkeypatch)
    monkeypatch.setattr(organizations_route, service_name, service_mock)
    monkeypatch.setattr(
        organizations_route,
        "search_organization_by_id",
        AsyncMock(return_value={"id": organization_id}),
    )
    monkeypatch.setattr(organizations_route, "check_organization_access", AsyncMock(return_value=True))

    response = await client.get(
        f"/v1/organizations/{organization_id}/statistics/{path_suffix}",
        headers=authenticated_headers,
    )

    assert response.status_code == 200
    assert response.json()["period"]["start_date"] == START_DATE.isoformat()
    service_mock.assert_awaited_once_with(organization_id, *service_args)
    _assert_cached_result(get_cached, set_cached, route_name, stats, ttl)
