"""
Integration tests for /v1/appointments routes.

Golden Rule for routes that use engine.begin() + internal search_*():
  - Patch search_*_by_id at the ROUTE level.
  - The mock intercepts the real RowMapping and converts it to dict(),
    avoiding the double-connection conflict (AttributeError: 'copy').
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.api.v1.routes import appointments as appointments_route
from app.api.v1.services import (
    appointment_service,
    customer_service,
    procedure_service,
    professional_service,
)
from tests.conftest import (
    api_create_org,
    api_create_owner,
    api_login_headers,
    api_register_root,
    setup_org_with_owner,
    unique_email,
    unique_name,
)

# ==========================================
# REAL-TO-DICT INTERCEPTORS
# ==========================================

original_search_appointment_by_id = appointment_service.search_appointment_by_id
original_search_procedure_by_id = procedure_service.search_procedure_by_id
original_search_professional_by_id = professional_service.search_professional_by_id
original_search_customer_by_id = customer_service.search_customer_by_id


async def search_appointment_as_dict(id: int):
    result = await original_search_appointment_by_id(id)
    return dict(result) if result is not None else None


async def search_procedure_as_dict(id: int):
    result = await original_search_procedure_by_id(id)
    return dict(result) if result is not None else None


async def search_professional_as_dict(id: int):
    result = await original_search_professional_by_id(id)
    return dict(result) if result is not None else None


async def search_customer_as_dict(id: int):
    result = await original_search_customer_by_id(id)
    return dict(result) if result is not None else None


# ==========================================
# SETUP FIXTURE HELPERS
# ==========================================

async def setup_appointment_prerequisites(client, root_headers: dict):
    """Creates Org, Owner, Staff User, Professional, Procedure, Customer, and Working Hours."""
    data = await setup_org_with_owner(client, root_headers)
    org_id = data["org"]["id"]
    owner_headers = data["owner_headers"]
    owner_id = data["owner"]["id"]

    # 1. Create Professional
    prof_resp = await client.post("/v1/professionals", json={
        "organization_id": org_id,
        "user_id": owner_id,
        "name": unique_name("Dr. Appt"),
        "buffer_time_minutes": 10,
        "is_active": True,
    }, headers=owner_headers)
    assert prof_resp.status_code == 201
    prof_id = int(prof_resp.json()["message"].split("PfID = ")[1].split(",")[0].rstrip("."))

    # 2. Create Procedure
    proc_resp = await client.post("/v1/procedures", json={
        "organization_id": org_id,
        "name": unique_name("Appt Procedure"),
        "duration_minutes": 30,
        "price": "100.00",
        "is_active": True,
    }, headers=owner_headers)
    assert proc_resp.status_code == 201
    proc_id = int(proc_resp.json()["message"].split("ProcedureID = ")[1].split(",")[0].rstrip("."))

    # 3. Link Professional to Procedure
    with patch("app.api.v1.routes.professionals.search_professional_by_id", new=search_professional_as_dict):
        link_resp = await client.post(f"/v1/professionals/{prof_id}/procedures", json={
            "organization_id": org_id,
            "procedure_id": proc_id,
            "is_active": True,
        }, headers=owner_headers)
        assert link_resp.status_code == 201

    # 4. Create Working Hours for all days of the week (1 to 7)
    with patch("app.api.v1.routes.professionals.search_professional_by_id", new=search_professional_as_dict):
        for day in range(1, 8):
            await client.post(f"/v1/professionals/{prof_id}/working-hours", json={
                "weekday": day,
                "start_time": "08:00:00",
                "end_time": "18:00:00",
                "is_active": True,
            }, headers=owner_headers)

    # 5. Create Customer
    cust_resp = await client.post("/v1/customers", json={
        "organization_id": org_id,
        "name": unique_name("Customer Appt"),
        "email": unique_email(),
        "phone": "+5511988888888",
        "is_active": True,
    }, headers=owner_headers)
    assert cust_resp.status_code == 201
    cust_id = int(cust_resp.json()["message"].split("CustomerID = ")[1].split(",")[0].rstrip("."))

    return {
        "org_id": org_id,
        "owner_headers": owner_headers,
        "prof_id": prof_id,
        "proc_id": proc_id,
        "cust_id": cust_id,
    }


# ==========================================
# POST /v1/appointments
# ==========================================

@pytest.mark.asyncio
async def test_create_appointment_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    setup = await setup_appointment_prerequisites(client, root_headers)

    # Next Monday at 10:00 AM
    now = datetime.now()
    days_ahead = (7 - now.weekday()) % 7 + 7  # ensure next week
    target_date = (now + timedelta(days=days_ahead)).replace(hour=10, minute=0, second=0, microsecond=0)

    with (
        patch.object(appointments_route, "search_procedure_by_id", new=search_procedure_as_dict),
        patch.object(appointments_route, "search_professional_by_id", new=search_professional_as_dict),
    ):
        response = await client.post("/v1/appointments", json={
            "organization_id": setup["org_id"],
            "customer_id": setup["cust_id"],
            "professional_id": setup["prof_id"],
            "procedure_id": setup["proc_id"],
            "start_at": target_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "SCHEDULED",
            "notes": "First appointment test",
        }, headers=setup["owner_headers"])

    assert response.status_code == 201
    assert "successfully created" in response.json()["message"]


@pytest.mark.asyncio
async def test_create_appointment_missing_entities_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    setup = await setup_appointment_prerequisites(client, root_headers)

    now = datetime.now()
    future = (now + timedelta(days=5)).strftime("%Y-%m-%dT10:00:00")

    response = await client.post("/v1/appointments", json={
        "organization_id": setup["org_id"],
        "customer_id": setup["cust_id"],
        "professional_id": 99999,  # non-existent professional
        "procedure_id": setup["proc_id"],
        "start_at": future,
        "status": "SCHEDULED",
    }, headers=setup["owner_headers"])

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_appointment_past_date_returns_422(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    setup = await setup_appointment_prerequisites(client, root_headers)

    past_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%dT10:00:00")

    with (
        patch.object(appointments_route, "search_procedure_by_id", new=search_procedure_as_dict),
        patch.object(appointments_route, "search_professional_by_id", new=search_professional_as_dict),
    ):
        response = await client.post("/v1/appointments", json={
            "organization_id": setup["org_id"],
            "customer_id": setup["cust_id"],
            "professional_id": setup["prof_id"],
            "procedure_id": setup["proc_id"],
            "start_at": past_date,
            "status": "SCHEDULED",
        }, headers=setup["owner_headers"])

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_appointment_no_token_returns_401(client):
    response = await client.post("/v1/appointments", json={
        "organization_id": 1,
        "customer_id": 1,
        "professional_id": 1,
        "procedure_id": 1,
        "start_at": "2099-01-01T10:00:00",
        "status": "SCHEDULED",
    })
    assert response.status_code == 401


# ==========================================
# GET /v1/appointments
# ==========================================

@pytest.mark.asyncio
async def test_list_appointments_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    setup = await setup_appointment_prerequisites(client, root_headers)

    response = await client.get(
        f"/v1/appointments?organization_id={setup['org_id']}",
        headers=setup["owner_headers"]
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_appointments_no_token_returns_401(client):
    response = await client.get("/v1/appointments?organization_id=1")
    assert response.status_code == 401


# ==========================================
# GET /v1/appointments/{id}
# ==========================================

@pytest.mark.asyncio
async def test_get_appointment_by_id_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.get("/v1/appointments/99999", headers=root_headers)
    assert response.status_code == 404


# ==========================================
# DELETE /v1/appointments/{id}  (Cancel)
# ==========================================

@pytest.mark.asyncio
async def test_cancel_appointment_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.delete("/v1/appointments/99999", headers=root_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_appointment_no_token_returns_401(client):
    response = await client.delete("/v1/appointments/1")
    assert response.status_code == 401
