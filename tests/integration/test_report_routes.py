"""Integration tests for root and organization report endpoints."""

from io import BytesIO, StringIO
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.v1.routes import organizations as organizations_route
from app.api.v1.routes.root import reports as root_reports_route
from app.api.v1.services.auth_service import verify_user_token
from app.main import app


REPORT_CASES = [
    (
        "appointments",
        "appointments",
        "generate_appointments_report",
        "Appointments Report",
        "appointments_report",
        {"org_id": None, "start_date": None, "end_date": None, "professional_id": None, "customer_id": None},
    ),
    (
        "revenue",
        "revenue",
        "generate_revenue_report",
        "Revenue Report",
        "revenue_report",
        {"org_id": None, "start_date": None, "end_date": None, "professional_id": None, "group_by": "month"},
    ),
    (
        "customers",
        "customers",
        "generate_customers_report",
        "Customers Report",
        "customers_report",
        {"org_id": None, "start_date": None, "end_date": None, "professional_id": None},
    ),
]


@pytest.fixture
def authenticated_headers(monkeypatch):
    async def return_test_user():
        return 17

    monkeypatch.setitem(app.dependency_overrides, verify_user_token, return_test_user)
    return {"Authorization": "Bearer report-test-token"}


def _report_data(title: str) -> dict:
    return {"metadata": {"report_title": title}, "summary": {"total": 1}, "data": []}


def _mock_download_generators(monkeypatch, route_module, format: str):
    if format == "csv":
        generator_name = "generate_csv_report"
        download_buffer = StringIO("report,csv\n")
        media_type = "text/csv"
        extension = "csv"
    else:
        generator_name = "generate_pdf_report"
        download_buffer = BytesIO(b"%PDF-test-report")
        media_type = "application/pdf"
        extension = "pdf"

    generator_mock = Mock(return_value=download_buffer)
    cache_mock = Mock()
    monkeypatch.setattr(route_module, generator_name, generator_mock)
    monkeypatch.setattr(route_module, "set_cached", cache_mock)
    return generator_name, generator_mock, cache_mock, download_buffer, media_type, extension


@pytest.mark.asyncio
@pytest.mark.parametrize("format", ["pdf", "csv"])
@pytest.mark.parametrize(
    ("kind", "path_suffix", "service_name", "title", "filename", "service_kwargs"),
    REPORT_CASES,
)
async def test_root_report_endpoints_generate_requested_file_and_cache_report(
    client,
    monkeypatch,
    authenticated_headers,
    format,
    kind,
    path_suffix,
    service_name,
    title,
    filename,
    service_kwargs,
):
    report_data = _report_data(title)
    service_mock = AsyncMock(return_value=report_data)
    monkeypatch.setattr(root_reports_route, service_name, service_mock)
    monkeypatch.setattr(root_reports_route, "is_root", AsyncMock(return_value=True))
    _, generator_mock, cache_mock, download_buffer, media_type, extension = _mock_download_generators(
        monkeypatch,
        root_reports_route,
        format,
    )

    response = await client.get(
        f"/v1/root/reports/{path_suffix}/global?format={format}",
        headers=authenticated_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(media_type)
    assert response.headers["content-disposition"] == f"attachment; filename={filename}.{extension}"
    expected_content = download_buffer.getvalue()
    if isinstance(expected_content, str):
        expected_content = expected_content.encode()
    assert response.content == expected_content
    service_mock.assert_awaited_once_with(**service_kwargs)
    generator_mock.assert_called_once_with(report_data)
    cache_mock.assert_called_once_with(
        f"cache:global_report_{kind}:None:None:None" + (":None" if kind == "appointments" else ":month" if kind == "revenue" else ""),
        report_data,
        ttl=300,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("format", ["pdf", "csv"])
@pytest.mark.parametrize(
    ("kind", "path_suffix", "service_name", "title", "filename", "service_kwargs"),
    REPORT_CASES,
)
async def test_organization_report_endpoints_generate_requested_file_and_cache_report(
    client,
    monkeypatch,
    authenticated_headers,
    format,
    kind,
    path_suffix,
    service_name,
    title,
    filename,
    service_kwargs,
):
    organization_id = 28
    report_data = _report_data(title)
    expected_service_kwargs = {**service_kwargs, "org_id": organization_id}
    service_mock = AsyncMock(return_value=report_data)
    monkeypatch.setattr(organizations_route, service_name, service_mock)
    monkeypatch.setattr(
        organizations_route,
        "search_organization_by_id",
        AsyncMock(return_value={"id": organization_id}),
    )
    monkeypatch.setattr(organizations_route, "check_organization_access", AsyncMock(return_value=True))
    _, generator_mock, cache_mock, download_buffer, media_type, extension = _mock_download_generators(
        monkeypatch,
        organizations_route,
        format,
    )

    response = await client.get(
        f"/v1/organizations/{organization_id}/reports/{path_suffix}?format={format}",
        headers=authenticated_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(media_type)
    assert response.headers["content-disposition"] == f"attachment; filename={filename}.{extension}"
    expected_content = download_buffer.getvalue()
    if isinstance(expected_content, str):
        expected_content = expected_content.encode()
    assert response.content == expected_content
    service_mock.assert_awaited_once_with(**expected_service_kwargs)
    generator_mock.assert_called_once_with(report_data)
    cache_key = f"cache:org_report_{kind}:None:None:None"
    if kind == "appointments":
        cache_key += ":None"
    elif kind == "revenue":
        cache_key += ":month"
    cache_mock.assert_called_once_with(cache_key, report_data, ttl=300)
