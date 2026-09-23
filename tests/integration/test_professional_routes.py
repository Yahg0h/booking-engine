"""
Integration tests for /v1/professionals routes.

Golden Rule for routes that use engine.begin() + internal search_*():
  - Patch search_professional_by_id at the ROUTE level.
  - The mock intercepts the real RowMapping and converts it to dict(),
    avoiding the double-connection conflict (AttributeError: 'copy').
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.api.v1.routes import professionals as professionals_route
from app.api.v1.services import professional_service
from tests.conftest import (
    api_create_org,
    api_create_owner,
    api_login_headers,
    api_register_root,
    setup_org_with_owner,
    unique_name,
)

# ==========================================
# REAL-TO-DICT INTERCEPTORS
# (Golden Rule: convert RowMapping -> dict at route level)
# ==========================================

original_search_professional_by_id = professional_service.search_professional_by_id


async def search_professional_as_dict(id: int):
    """Return the real professional row as a plain dict instead of RowMapping."""
    result = await original_search_professional_by_id(id)
    return dict(result) if result is not None else None


# ==========================================
# HELPERS
# ==========================================

async def api_create_professional(client, owner_headers: dict, org_id: int, owner_user_id: int) -> dict:
    """Helper to create a professional under an org."""
    payload = {
        "organization_id": org_id,
        "user_id": owner_user_id,
        "name": unique_name("Pro"),
        "buffer_time_minutes": 10,
        "is_active": True,
    }
    resp = await client.post("/v1/professionals", json=payload, headers=owner_headers)
    assert resp.status_code == 201, f"Professional creation failed: {resp.text}"
    # Parse the id from the response message
    # "Professional successfully created. OrgID = X, PfID = Y, UserID = Z."
    msg = resp.json()["message"]
    prof_id = int(msg.split("PfID = ")[1].split(",")[0].rstrip("."))
    return {"id": prof_id, **payload}


# ==========================================
# POST /v1/professionals
# ==========================================

@pytest.mark.asyncio
async def test_create_professional_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.post("/v1/professionals", json={
        "organization_id": data["org"]["id"],
        "user_id": data["owner"]["id"],
        "name": unique_name("Pro"),
        "buffer_time_minutes": 10,
        "is_active": True,
    }, headers=data["owner_headers"])
    assert response.status_code == 201
    assert "PfID" in response.json()["message"]


@pytest.mark.asyncio
async def test_create_professional_as_root_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    org = await api_create_org(client, root_headers)
    owner = await api_create_owner(client, root_headers, org["id"])

    response = await client.post("/v1/professionals", json={
        "organization_id": org["id"],
        "user_id": owner["id"],
        "name": unique_name("Pro Root"),
        "buffer_time_minutes": 5,
        "is_active": True,
    }, headers=root_headers)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_professional_no_token_returns_401(client):
    response = await client.post("/v1/professionals", json={
        "organization_id": 1,
        "user_id": 1,
        "name": "Ghost Pro",
        "buffer_time_minutes": 0,
        "is_active": True,
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_professional_wrong_org_returns_403(client):
    """Owner of org A cannot create a professional under org B."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data_a = await setup_org_with_owner(client, root_headers)
    org_b = await api_create_org(client, root_headers)

    response = await client.post("/v1/professionals", json={
        "organization_id": org_b["id"],
        "user_id": data_a["owner"]["id"],
        "name": unique_name("Intruder"),
        "buffer_time_minutes": 0,
        "is_active": True,
    }, headers=data_a["owner_headers"])
    assert response.status_code == 403


# ==========================================
# GET /v1/professionals  (list by org)
# ==========================================

@pytest.mark.asyncio
async def test_get_professionals_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.get(
        f"/v1/professionals?organization_id={data['org']['id']}",
        headers=data["owner_headers"]
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_professionals_no_token_returns_401(client):
    response = await client.get("/v1/professionals?organization_id=1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_professionals_wrong_org_returns_403(client):
    """Owner of org A cannot list professionals of org B."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data_a = await setup_org_with_owner(client, root_headers)
    org_b = await api_create_org(client, root_headers)

    response = await client.get(
        f"/v1/professionals?organization_id={org_b['id']}",
        headers=data_a["owner_headers"]
    )
    assert response.status_code == 403


# ==========================================
# GET /v1/professionals/all  (root-only)
# ==========================================

@pytest.mark.asyncio
async def test_get_all_professionals_as_root_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.get("/v1/professionals/all", headers=root_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_all_professionals_as_owner_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.get("/v1/professionals/all", headers=data["owner_headers"])
    assert response.status_code == 403


# ==========================================
# GET /v1/professionals/{id}  (public)
# ==========================================

@pytest.mark.asyncio
async def test_get_professional_by_id_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.get(f"/v1/professionals/{prof['id']}")

    assert response.status_code == 200
    body = response.json()
    assert "name" in body
    assert "organization_id" in body
    assert "user_id" in body


@pytest.mark.asyncio
async def test_get_professional_by_id_not_found_returns_404(client):
    response = await client.get("/v1/professionals/99999")
    assert response.status_code == 404


# ==========================================
# PATCH /v1/professionals/{id}
# ==========================================

@pytest.mark.asyncio
async def test_update_professional_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.patch(
            f"/v1/professionals/{prof['id']}",
            json={"name": unique_name("Updated Pro")},
            headers=data["owner_headers"]
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_professional_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.patch(
        "/v1/professionals/99999",
        json={"name": "Ghost"},
        headers=root_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_professional_no_token_returns_401(client):
    response = await client.patch("/v1/professionals/1", json={"name": "Ghost"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_professional_wrong_org_returns_403(client):
    """Owner of org A cannot update a professional from org B."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data_a = await setup_org_with_owner(client, root_headers)
    data_b = await setup_org_with_owner(client, root_headers)
    prof_b = await api_create_professional(client, data_b["owner_headers"], data_b["org"]["id"], data_b["owner"]["id"])

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.patch(
            f"/v1/professionals/{prof_b['id']}",
            json={"name": "Hijacked"},
            headers=data_a["owner_headers"]
        )
    assert response.status_code == 403


# ==========================================
# DELETE /v1/professionals/{id}
# ==========================================

@pytest.mark.asyncio
async def test_delete_professional_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.delete(
            f"/v1/professionals/{prof['id']}",
            headers=data["owner_headers"]
        )
    assert response.status_code == 200
    assert "deactivated" in response.json()["message"]


@pytest.mark.asyncio
async def test_delete_professional_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.delete("/v1/professionals/99999", headers=root_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_professional_no_token_returns_401(client):
    response = await client.delete("/v1/professionals/1")
    assert response.status_code == 401


# ==========================================
# POST /v1/professionals/{id}/working-hours
# ==========================================

@pytest.mark.asyncio
async def test_create_working_hour_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.post(
            f"/v1/professionals/{prof['id']}/working-hours",
            json={
                "weekday": 1,
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "is_active": True,
            },
            headers=data["owner_headers"]
        )
    assert response.status_code in (200, 201)


@pytest.mark.asyncio
async def test_create_working_hour_duplicate_weekday_returns_409(client):
    """Creating a second working hour for the same weekday must return 409."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    wh_payload = {
        "weekday": 2,
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "is_active": True,
    }

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        # First creation
        resp1 = await client.post(
            f"/v1/professionals/{prof['id']}/working-hours",
            json=wh_payload,
            headers=data["owner_headers"]
        )
        assert resp1.status_code in (200, 201)

        # Second creation with same weekday
        resp2 = await client.post(
            f"/v1/professionals/{prof['id']}/working-hours",
            json=wh_payload,
            headers=data["owner_headers"]
        )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_working_hour_no_token_returns_401(client):
    response = await client.post(
        "/v1/professionals/1/working-hours",
        json={"weekday": 1, "start_time": "09:00:00", "end_time": "17:00:00", "is_active": True}
    )
    assert response.status_code == 401


# ==========================================
# GET /v1/professionals/{professional_id}/working-hours  (public)
# ==========================================

@pytest.mark.asyncio
async def test_get_working_hours_by_professional_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.get(f"/v1/professionals/{prof['id']}/working-hours")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_working_hours_professional_not_found_returns_404(client):
    response = await client.get("/v1/professionals/99999/working-hours")
    assert response.status_code == 404


# ==========================================
# POST /v1/professionals/{id}/blackouts
# ==========================================

@pytest.mark.asyncio
async def test_create_blackout_as_professional_owner_success(client):
    """The professional's own user_id must match the token user_id."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    future_start = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")
    future_end = (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%S")

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.post(
            f"/v1/professionals/{prof['id']}/blackouts",
            json={
                "start_at": future_start,
                "end_at": future_end,
                "reason": "Vacation",
            },
            headers=data["owner_headers"]
        )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_blackout_past_date_returns_422(client):
    """Blackout dates in the past must be rejected."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    past_start = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S")
    past_end = (datetime.now(timezone.utc) - timedelta(days=9)).strftime("%Y-%m-%dT%H:%M:%S")

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.post(
            f"/v1/professionals/{prof['id']}/blackouts",
            json={
                "start_at": past_start,
                "end_at": past_end,
                "reason": "Past",
            },
            headers=data["owner_headers"]
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_blackout_wrong_user_returns_403(client):
    """A different user cannot create a blackout for a professional they don't own."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data_a = await setup_org_with_owner(client, root_headers)
    data_b = await setup_org_with_owner(client, root_headers)
    # Create professional belonging to owner_a
    prof_a = await api_create_professional(client, data_a["owner_headers"], data_a["org"]["id"], data_a["owner"]["id"])

    future_start = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")
    future_end = (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%S")

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        # owner_b tries to create a blackout for owner_a's professional
        response = await client.post(
            f"/v1/professionals/{prof_a['id']}/blackouts",
            json={"start_at": future_start, "end_at": future_end, "reason": "Intruder"},
            headers=data_b["owner_headers"]
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_blackout_no_token_returns_401(client):
    response = await client.post(
        "/v1/professionals/1/blackouts",
        json={
            "start_at": "2099-01-01T09:00:00",
            "end_at": "2099-01-02T09:00:00",
            "reason": "Test",
        }
    )
    assert response.status_code == 401


# ==========================================
# GET /v1/professionals/{id}/blackouts
# ==========================================

@pytest.mark.asyncio
async def test_get_blackouts_by_professional_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.get(
            f"/v1/professionals/{prof['id']}/blackouts",
            headers=data["owner_headers"]
        )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_blackouts_professional_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.get("/v1/professionals/99999/blackouts", headers=root_headers)
    assert response.status_code == 404


# ==========================================
# POST /v1/blackouts/{id}/approve and /reject
# ==========================================

@pytest.mark.asyncio
async def test_approve_blackout_as_owner_returns_accepted(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    future_start = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")
    future_end = (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%S")

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        create_response = await client.post(
            f"/v1/professionals/{prof['id']}/blackouts",
            json={"start_at": future_start, "end_at": future_end, "reason": "Vacation"},
            headers=data["owner_headers"],
        )

    assert create_response.status_code == 201
    blackout_id = int(create_response.json()["message"].split("BlackoutID = ")[1].rstrip("."))

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.post(f"/v1/blackouts/{blackout_id}/approve", headers=data["owner_headers"])

    assert response.status_code == 200
    assert response.json()["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_reject_blackout_as_owner_returns_rejected(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    future_start = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    future_end = (datetime.now(timezone.utc) + timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%S")

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        create_response = await client.post(
            f"/v1/professionals/{prof['id']}/blackouts",
            json={"start_at": future_start, "end_at": future_end, "reason": "Personal"},
            headers=data["owner_headers"],
        )

    assert create_response.status_code == 201
    blackout_id = int(create_response.json()["message"].split("BlackoutID = ")[1].rstrip("."))

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.post(f"/v1/blackouts/{blackout_id}/reject", headers=data["owner_headers"])

    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"


# ==========================================
# POST /v1/professionals/{id}/procedures
# ==========================================

@pytest.mark.asyncio
async def test_create_professional_procedure_as_owner_success(client):
    """Linking a procedure to a professional must return 201."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    # Create a procedure first
    proc_resp = await client.post("/v1/procedures", json={
        "organization_id": data["org"]["id"],
        "name": unique_name("Proc"),
        "description": "Test",
        "duration_minutes": 30,
        "price": "50.00",
        "is_active": True,
    }, headers=data["owner_headers"])
    assert proc_resp.status_code == 201
    proc_id = int(proc_resp.json()["message"].split("ProcedureID = ")[1].split(",")[0].rstrip("."))

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.post(
            f"/v1/professionals/{prof['id']}/procedures",
            json={
                "organization_id": data["org"]["id"],
                "procedure_id": proc_id,
                "is_active": True,
            },
            headers=data["owner_headers"]
        )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_pp_professional_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.post(
        "/v1/professionals/99999/procedures",
        json={"organization_id": 1, "procedure_id": 1, "is_active": True},
        headers=root_headers
    )
    assert response.status_code == 404


# ==========================================
# GET /v1/professionals/{id}/procedures  (public)
# ==========================================

@pytest.mark.asyncio
async def test_get_procedures_by_professional_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    prof = await api_create_professional(client, data["owner_headers"], data["org"]["id"], data["owner"]["id"])

    with patch.object(professionals_route, "search_professional_by_id", new=search_professional_as_dict):
        response = await client.get(f"/v1/professionals/{prof['id']}/procedures")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_procedures_by_professional_not_found_returns_404(client):
    response = await client.get("/v1/professionals/99999/procedures")
    assert response.status_code == 404
