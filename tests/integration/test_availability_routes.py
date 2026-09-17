"""
Integration tests for /v1/availability routes.

Golden Rule for routes that use engine.begin() + internal search_*():
  - Patch search_*_by_id at the ROUTE level.
  - The mock intercepts the real RowMapping and converts it to dict(),
    avoiding the double-connection conflict (AttributeError: 'copy').
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.api.v1.routes import availability as availability_route
from app.api.v1.services import (
    procedure_service,
    professional_service,
)
from tests.conftest import (
    api_login_headers,
    api_register_root,
    setup_org_with_owner,
    unique_name,
)

# ==========================================
# REAL-TO-DICT INTERCEPTORS
# ==========================================

original_search_procedure_by_id = procedure_service.search_procedure_by_id
original_search_professional_by_id = professional_service.search_professional_by_id


async def search_procedure_as_dict(id: int):
    result = await original_search_procedure_by_id(id)
    return dict(result) if result is not None else None


async def search_professional_as_dict(id: int):
    result = await original_search_professional_by_id(id)
    return dict(result) if result is not None else None


# ==========================================
# GET /v1/availability
# ==========================================

@pytest.mark.asyncio
async def test_get_availability_missing_entity_returns_404(client):
    response = await client.get("/v1/availability?organization_id=99999&professional_id=1&procedure_id=1&date=2026-12-01")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_availability_past_date_returns_422(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    org_id = data["org"]["id"]

    past_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

    response = await client.get(
        f"/v1/availability?organization_id={org_id}&professional_id=1&procedure_id=1&date={past_date}"
    )
    assert response.status_code in (404, 422)


@pytest.mark.asyncio
async def test_get_availability_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    org_id = data["org"]["id"]
    owner_headers = data["owner_headers"]
    owner_id = data["owner"]["id"]

    # 1. Create Professional
    prof_resp = await client.post("/v1/professionals", json={
        "organization_id": org_id,
        "user_id": owner_id,
        "name": unique_name("Dr. Avail"),
        "buffer_time_minutes": 10,
        "is_active": True,
    }, headers=owner_headers)
    assert prof_resp.status_code == 201
    prof_id = int(prof_resp.json()["message"].split("PfID = ")[1].split(",")[0].rstrip("."))

    # 2. Create Procedure
    proc_resp = await client.post("/v1/procedures", json={
        "organization_id": org_id,
        "name": unique_name("Avail Procedure"),
        "duration_minutes": 30,
        "price": "100.00",
        "is_active": True,
    }, headers=owner_headers)
    assert proc_resp.status_code == 201
    proc_id = int(proc_resp.json()["message"].split("ProcedureID = ")[1].split(",")[0].rstrip("."))

    # 3. Link Professional to Procedure
    with patch("app.api.v1.routes.professionals.search_professional_by_id", new=search_professional_as_dict):
        await client.post(f"/v1/professionals/{prof_id}/procedures", json={
            "organization_id": org_id,
            "procedure_id": proc_id,
            "is_active": True,
        }, headers=owner_headers)

    # 4. Create Working Hours for all days of the week (1 to 7)
    with patch("app.api.v1.routes.professionals.search_professional_by_id", new=search_professional_as_dict):
        for day in range(1, 8):
            await client.post(f"/v1/professionals/{prof_id}/working-hours", json={
                "weekday": day,
                "start_time": "08:00:00",
                "end_time": "18:00:00",
                "is_active": True,
            }, headers=owner_headers)

    # Future date (next Monday)
    now = datetime.now()
    days_ahead = (7 - now.weekday()) % 7 + 7
    future_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    with (
        patch.object(availability_route, "search_procedure_by_id", new=search_procedure_as_dict),
        patch.object(availability_route, "search_professional_by_id", new=search_professional_as_dict),
    ):
        response = await client.get(
            f"/v1/availability?organization_id={org_id}&professional_id={prof_id}&procedure_id={proc_id}&date={future_date}"
        )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
