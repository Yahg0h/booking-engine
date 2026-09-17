"""
Integration tests for /v1/customers routes.

Golden Rule for routes that use engine.begin() + internal search_*():
  - Patch search_customer_by_id at the ROUTE level.
  - The mock intercepts the real RowMapping and converts it to dict(),
    avoiding the double-connection conflict (AttributeError: 'copy').
"""

from unittest.mock import patch

import pytest

from app.api.v1.routes import customers as customers_route
from app.api.v1.services import customer_service
from tests.conftest import (
    api_create_org,
    api_create_staff,
    api_login_headers,
    api_register_root,
    setup_org_with_owner,
    unique_email,
    unique_name,
)

# ==========================================
# REAL-TO-DICT INTERCEPTORS
# ==========================================

original_search_customer_by_id = customer_service.search_customer_by_id


async def search_customer_as_dict(customer_id: int):
    """Return the real customer row as a plain dict instead of RowMapping."""
    result = await original_search_customer_by_id(customer_id)
    return dict(result) if result is not None else None


# ==========================================
# HELPERS
# ==========================================

async def api_create_customer(client, headers: dict, org_id: int, **overrides) -> dict:
    payload = {
        "organization_id": org_id,
        "name": unique_name("Customer"),
        "email": unique_email(),
        "phone": "+5511999999999",
        "is_active": True,
        **overrides,
    }
    resp = await client.post("/v1/customers", json=payload, headers=headers)
    assert resp.status_code == 201, f"Customer creation failed: {resp.text}"
    msg = resp.json()["message"]
    customer_id = int(msg.split("CustomerID = ")[1].split(",")[0].rstrip("."))
    return {"id": customer_id, **payload}


# ==========================================
# POST /v1/customers
# ==========================================

@pytest.mark.asyncio
async def test_create_customer_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.post("/v1/customers", json={
        "organization_id": data["org"]["id"],
        "name": unique_name("Customer"),
        "email": unique_email(),
        "phone": "+5511999999999",
        "is_active": True,
    }, headers=data["owner_headers"])

    assert response.status_code == 201
    assert "CustomerID" in response.json()["message"]


@pytest.mark.asyncio
async def test_create_customer_as_staff_success(client):
    from tests.integration.test_professional_routes import api_create_professional

    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    # Create professional record for staff so check_customer_access recognizes staff member
    await api_create_professional(client, data["owner_headers"], data["org"]["id"], staff["id"])
    staff_headers = await api_login_headers(client, staff["email"], staff["password"])

    response = await client.post("/v1/customers", json={
        "organization_id": data["org"]["id"],
        "name": unique_name("Customer Staff"),
        "email": unique_email(),
        "phone": "+5511999999999",
        "is_active": True,
    }, headers=staff_headers)

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_customer_no_token_returns_401(client):
    response = await client.post("/v1/customers", json={
        "organization_id": 1,
        "name": "Ghost",
        "email": unique_email(),
        "phone": "+5511999999999",
        "is_active": True,
    })

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_customer_no_contact_returns_422(client):
    """Schema validation: customer must have at least email or phone."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.post("/v1/customers", json={
        "organization_id": data["org"]["id"],
        "name": unique_name("No Contact"),
        "email": None,
        "phone": None,
        "is_active": True,
    }, headers=data["owner_headers"])

    assert response.status_code == 422


# ==========================================
# GET /v1/customers
# ==========================================

@pytest.mark.asyncio
async def test_list_customers_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    await api_create_customer(client, data["owner_headers"], data["org"]["id"])

    response = await client.get(
        f"/v1/customers?organization_id={data['org']['id']}",
        headers=data["owner_headers"]
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_customers_no_token_returns_401(client):
    response = await client.get("/v1/customers?organization_id=1&email=&phone=&last_appointment_at=")
    assert response.status_code == 401


# ==========================================
# GET /v1/customers/{id}
# ==========================================

@pytest.mark.asyncio
async def test_get_customer_by_id_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    cust = await api_create_customer(client, data["owner_headers"], data["org"]["id"])

    with patch.object(customers_route, "search_customer_by_id", new=search_customer_as_dict):
        response = await client.get(f"/v1/customers/{cust['id']}", headers=data["owner_headers"])

    assert response.status_code == 200
    assert response.json()["id"] == cust["id"]


@pytest.mark.asyncio
async def test_get_customer_by_id_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.get("/v1/customers/99999", headers=root_headers)
    assert response.status_code == 404


# ==========================================
# PATCH /v1/customers/{id}
# ==========================================

@pytest.mark.asyncio
async def test_update_customer_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    cust = await api_create_customer(client, data["owner_headers"], data["org"]["id"])

    with (
        patch.object(customer_service, "search_customer_by_id", new=search_customer_as_dict),
        patch.object(customers_route, "search_customer_by_id", new=search_customer_as_dict),
    ):
        response = await client.patch(
            f"/v1/customers/{cust['id']}",
            json={"name": unique_name("Updated Cust")},
            headers=data["owner_headers"]
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_customer_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.patch(
        "/v1/customers/99999",
        json={"name": "Ghost"},
        headers=root_headers
    )
    assert response.status_code == 404


# ==========================================
# DELETE /v1/customers/{id}
# ==========================================

@pytest.mark.asyncio
async def test_delete_customer_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    cust = await api_create_customer(client, data["owner_headers"], data["org"]["id"])

    with (
        patch.object(customer_service, "search_customer_by_id", new=search_customer_as_dict),
        patch.object(customers_route, "search_customer_by_id", new=search_customer_as_dict),
    ):
        response = await client.delete(
            f"/v1/customers/{cust['id']}",
            headers=data["owner_headers"]
        )

    assert response.status_code == 200
    assert "deactivated" in response.json()["message"]


@pytest.mark.asyncio
async def test_delete_customer_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.delete("/v1/customers/99999", headers=root_headers)
    assert response.status_code == 404
