"""
Integration tests for /v1/procedures routes.

Golden Rule for routes that use engine.begin() + internal search_*():
  - Patch search_procedure_by_id at the ROUTE level.
  - The mock intercepts the real RowMapping and converts it to dict(),
    avoiding the double-connection conflict (AttributeError: 'copy').
"""

from unittest.mock import patch

import pytest

from app.api.v1.routes import procedures as procedures_route
from app.api.v1.services import procedure_service
from tests.conftest import (
    api_create_org,
    api_login_headers,
    api_register_root,
    setup_org_with_owner,
    unique_name,
)

# ==========================================
# REAL-TO-DICT INTERCEPTORS
# (Golden Rule: convert RowMapping -> dict at route level)
# ==========================================

original_search_procedure_by_id = procedure_service.search_procedure_by_id


async def search_procedure_as_dict(id: int):
    """Return the real procedure row as a plain dict instead of RowMapping."""
    result = await original_search_procedure_by_id(id)
    return dict(result) if result is not None else None


# ==========================================
# HELPERS
# ==========================================

async def api_create_procedure(client, owner_headers: dict, org_id: int, **overrides) -> dict:
    """Helper to create a procedure under an org."""
    payload = {
        "organization_id": org_id,
        "name": unique_name("Proc"),
        "description": "Test procedure",
        "duration_minutes": 30,
        "price": "50.00",
        "is_active": True,
        **overrides,
    }
    resp = await client.post("/v1/procedures", json=payload, headers=owner_headers)
    assert resp.status_code == 201, f"Procedure creation failed: {resp.text}"
    # "Procedure successfully created. ProcedureID = X, OrgID = Y"
    msg = resp.json()["message"]
    proc_id = int(msg.split("ProcedureID = ")[1].split(",")[0].rstrip("."))
    return {"id": proc_id, **payload}


# ==========================================
# POST /v1/procedures
# ==========================================

@pytest.mark.asyncio
async def test_create_procedure_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.post("/v1/procedures", json={
        "organization_id": data["org"]["id"],
        "name": unique_name("Haircut"),
        "description": "A classic haircut",
        "duration_minutes": 30,
        "price": "50.00",
        "is_active": True,
    }, headers=data["owner_headers"])
    assert response.status_code == 201
    assert "ProcedureID" in response.json()["message"]


@pytest.mark.asyncio
async def test_create_procedure_as_root_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    org = await api_create_org(client, root_headers)

    response = await client.post("/v1/procedures", json={
        "organization_id": org["id"],
        "name": unique_name("Root Proc"),
        "duration_minutes": 60,
        "price": "100.00",
        "is_active": True,
    }, headers=root_headers)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_procedure_no_token_returns_401(client):
    response = await client.post("/v1/procedures", json={
        "organization_id": 1,
        "name": "Ghost Proc",
        "duration_minutes": 30,
        "price": "0.00",
        "is_active": True,
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_procedure_wrong_org_returns_403(client):
    """Owner of org A cannot create a procedure for org B."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data_a = await setup_org_with_owner(client, root_headers)
    org_b = await api_create_org(client, root_headers)

    response = await client.post("/v1/procedures", json={
        "organization_id": org_b["id"],
        "name": unique_name("Intruder Proc"),
        "duration_minutes": 30,
        "price": "50.00",
        "is_active": True,
    }, headers=data_a["owner_headers"])
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_procedure_invalid_duration_returns_422(client):
    """duration_minutes must be greater than 0 (Pydantic validation)."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.post("/v1/procedures", json={
        "organization_id": data["org"]["id"],
        "name": unique_name("BadDuration"),
        "duration_minutes": 0,   # invalid: must be > 0
        "price": "50.00",
        "is_active": True,
    }, headers=data["owner_headers"])
    assert response.status_code == 422


# ==========================================
# GET /v1/procedures/organization/{id}  (public)
# ==========================================

@pytest.mark.asyncio
async def test_get_procedures_by_organization_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    await api_create_procedure(client, data["owner_headers"], data["org"]["id"])

    response = await client.get(f"/v1/procedures/organization/{data['org']['id']}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_procedures_by_organization_not_found_returns_404(client):
    response = await client.get("/v1/procedures/organization/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_procedures_by_organization_is_active_false(client):
    """Querying inactive procedures must return a list (even if empty)."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.get(
        f"/v1/procedures/organization/{data['org']['id']}?is_active=false"
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ==========================================
# GET /v1/procedures/{id}  (public)
# ==========================================

@pytest.mark.asyncio
async def test_get_procedure_by_id_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    proc = await api_create_procedure(client, data["owner_headers"], data["org"]["id"])

    with patch.object(procedures_route, "search_procedure_by_id", new=search_procedure_as_dict):
        response = await client.get(f"/v1/procedures/{proc['id']}")

    assert response.status_code == 200
    body = response.json()
    assert "name" in body
    assert "duration_minutes" in body


@pytest.mark.asyncio
async def test_get_procedure_by_id_not_found_returns_404(client):
    response = await client.get("/v1/procedures/99999")
    assert response.status_code == 404


# ==========================================
# PATCH /v1/procedures/{id}
# ==========================================

@pytest.mark.asyncio
async def test_update_procedure_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    proc = await api_create_procedure(client, data["owner_headers"], data["org"]["id"])

    with patch.object(procedures_route, "search_procedure_by_id", new=search_procedure_as_dict):
        response = await client.patch(
            f"/v1/procedures/{proc['id']}",
            json={"name": unique_name("Updated Proc")},
            headers=data["owner_headers"]
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_procedure_as_root_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    proc = await api_create_procedure(client, data["owner_headers"], data["org"]["id"])

    with patch.object(procedures_route, "search_procedure_by_id", new=search_procedure_as_dict):
        response = await client.patch(
            f"/v1/procedures/{proc['id']}",
            json={"name": unique_name("Root Updated"), "price": "99.99"},
            headers=root_headers
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_procedure_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.patch(
        "/v1/procedures/99999",
        json={"name": "Ghost"},
        headers=root_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_procedure_no_token_returns_401(client):
    response = await client.patch("/v1/procedures/1", json={"name": "Ghost"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_procedure_wrong_org_returns_403(client):
    """Owner of org A cannot update a procedure from org B."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data_a = await setup_org_with_owner(client, root_headers)
    data_b = await setup_org_with_owner(client, root_headers)
    proc_b = await api_create_procedure(client, data_b["owner_headers"], data_b["org"]["id"])

    with patch.object(procedures_route, "search_procedure_by_id", new=search_procedure_as_dict):
        response = await client.patch(
            f"/v1/procedures/{proc_b['id']}",
            json={"name": "Hijacked"},
            headers=data_a["owner_headers"]
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_procedure_is_active_false_deactivates(client):
    """
    Patching is_active=False must succeed (not silently skip the False value).
    This tests the is_active is not None guard at the service level.
    """
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    proc = await api_create_procedure(client, data["owner_headers"], data["org"]["id"])

    with patch.object(procedures_route, "search_procedure_by_id", new=search_procedure_as_dict):
        response = await client.patch(
            f"/v1/procedures/{proc['id']}",
            json={"is_active": False},
            headers=data["owner_headers"]
        )
    assert response.status_code == 200


# ==========================================
# DELETE /v1/procedures/{id}
# ==========================================

@pytest.mark.asyncio
async def test_delete_procedure_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    proc = await api_create_procedure(client, data["owner_headers"], data["org"]["id"])

    with patch.object(procedures_route, "search_procedure_by_id", new=search_procedure_as_dict):
        response = await client.delete(
            f"/v1/procedures/{proc['id']}",
            headers=data["owner_headers"]
        )
    assert response.status_code == 200
    assert "deactivated" in response.json()["message"]


@pytest.mark.asyncio
async def test_delete_procedure_as_root_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    proc = await api_create_procedure(client, data["owner_headers"], data["org"]["id"])

    with patch.object(procedures_route, "search_procedure_by_id", new=search_procedure_as_dict):
        response = await client.delete(
            f"/v1/procedures/{proc['id']}",
            headers=root_headers
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_procedure_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.delete("/v1/procedures/99999", headers=root_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_procedure_no_token_returns_401(client):
    response = await client.delete("/v1/procedures/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_procedure_wrong_org_returns_403(client):
    """Owner of org A cannot delete a procedure from org B."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data_a = await setup_org_with_owner(client, root_headers)
    data_b = await setup_org_with_owner(client, root_headers)
    proc_b = await api_create_procedure(client, data_b["owner_headers"], data_b["org"]["id"])

    with patch.object(procedures_route, "search_procedure_by_id", new=search_procedure_as_dict):
        response = await client.delete(
            f"/v1/procedures/{proc_b['id']}",
            headers=data_a["owner_headers"]
        )
    assert response.status_code == 403
