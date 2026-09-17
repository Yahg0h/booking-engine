from unittest.mock import patch

import pytest

from app.api.v1.routes import users as users_route
from app.api.v1.services import user_service
from tests.conftest import (
    api_create_org,
    api_create_owner,
    api_create_staff,
    api_login_headers,
    api_register_root,
    setup_org_with_owner,
    unique_email,
    unique_name,
)

original_search_user_by_id = user_service.search_user_by_id



async def search_user_as_dict(user_id: int):
    """Return the real user row as a plain dict instead of RowMapping."""
    result = await original_search_user_by_id(user_id)
    return dict(result) if result is not None else None


# ==========================================
# POST /v1/users  (create staff)
# ==========================================

@pytest.mark.asyncio
async def test_create_staff_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.post("/v1/users", json={
        "name": unique_name("Staff"),
        "email": unique_email(),
        "password": "staffpass123",
        "role": "STAFF",
        "organization_id": data["org"]["id"],
        "is_active": True
    }, headers=data["owner_headers"])
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_staff_as_staff_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_headers = await api_login_headers(client, staff["email"], staff["password"])

    response = await client.post("/v1/users", json={
        "name": unique_name("Staff"),
        "email": unique_email(),
        "password": "staffpass123",
        "role": "STAFF",
        "organization_id": data["org"]["id"],
        "is_active": True
    }, headers=staff_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_staff_duplicate_email_returns_409(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    email = unique_email()

    await client.post("/v1/users", json={
        "name": unique_name("Staff"),
        "email": email,
        "password": "staffpass123",
        "role": "STAFF",
        "organization_id": data["org"]["id"],
        "is_active": True
    }, headers=data["owner_headers"])

    response = await client.post("/v1/users", json={
        "name": unique_name("Staff"),
        "email": email,  # same email
        "password": "staffpass123",
        "role": "STAFF",
        "organization_id": data["org"]["id"],
        "is_active": True
    }, headers=data["owner_headers"])
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_staff_no_token_returns_401(client):
    response = await client.post("/v1/users", json={
        "name": "Ghost",
        "email": unique_email(),
        "password": "staffpass123",
        "role": "STAFF",
        "organization_id": 1,
        "is_active": True
    })
    assert response.status_code == 401


# ==========================================
# POST /v1/users/owners
# ==========================================

@pytest.mark.asyncio
async def test_create_owner_as_root_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    org = await api_create_org(client, root_headers)

    response = await client.post("/v1/users/owners", json={
        "name": unique_name("Owner"),
        "email": unique_email(),
        "password": "ownerpass123",
        "role": "OWNER",
        "organization_id": org["id"],
        "is_active": True
    }, headers=root_headers)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_owner_as_owner_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.post("/v1/users/owners", json={
        "name": unique_name("Owner"),
        "email": unique_email(),
        "password": "ownerpass123",
        "role": "OWNER",
        "organization_id": data["org"]["id"],
        "is_active": True
    }, headers=data["owner_headers"])
    assert response.status_code == 403


# ==========================================
# GET /v1/users
# ==========================================

@pytest.mark.asyncio
async def test_get_users_as_root_returns_200(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.get("/v1/users", headers=root_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_users_as_staff_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_headers = await api_login_headers(client, staff["email"], staff["password"])

    response = await client.get("/v1/users", headers=staff_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_users_no_token_returns_401(client):
    response = await client.get("/v1/users")
    assert response.status_code == 401


# ==========================================
# GET /v1/users/{id}
# ==========================================

@pytest.mark.asyncio
async def test_get_user_by_id_as_owner_returns_200(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])

    response = await client.get(f"/v1/users/{staff['id']}", headers=data["owner_headers"])
    assert response.status_code == 200
    assert response.json()["id"] == staff["id"]


@pytest.mark.asyncio
async def test_get_user_by_id_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.get("/v1/users/99999", headers=root_headers)
    assert response.status_code == 404


# ==========================================
# PATCH /v1/users/{id}  (own profile)
# ==========================================

@pytest.mark.asyncio
async def test_update_own_profile_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    password = "mypassword123"
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"], password=password)
    staff_headers = await api_login_headers(client, staff["email"], staff["password"])

    with (
        patch.object(user_service, "search_user_by_id", new=search_user_as_dict),
        patch.object(users_route, "search_user_by_id", new=search_user_as_dict),
    ):
        response = await client.patch(
            f"/v1/users/{staff['id']}",
            json={"name": unique_name("Updated"), "current_password": password},
            headers=staff_headers
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_own_profile_wrong_password_returns_401(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_headers = await api_login_headers(client, staff["email"], staff["password"])

    response = await client.patch(
        f"/v1/users/{staff['id']}",
        json={"name": "Hacker", "current_password": "wrongpassword"},
        headers=staff_headers
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_other_user_own_endpoint_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff_a = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_b = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_a_headers = await api_login_headers(client, staff_a["email"], staff_a["password"])

    # staff_a tries to update staff_b via own-profile endpoint
    response = await client.patch(
        f"/v1/users/{staff_b['id']}",
        json={"name": "Intruder", "current_password": "testpass123"},
        headers=staff_a_headers
    )
    assert response.status_code == 403


# ==========================================
# PATCH /v1/users/admin/update/{id}
# ==========================================

@pytest.mark.asyncio
async def test_admin_update_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])

    with (
        patch.object(user_service, "search_user_by_id", new=search_user_as_dict),
        patch.object(users_route, "search_user_by_id", new=search_user_as_dict),
    ):
        response = await client.patch(
            f"/v1/users/admin/update/{staff['id']}",
            json={"name": unique_name("Admin Updated")},
            headers=data["owner_headers"]
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_update_as_staff_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff_a = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_b = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_a_headers = await api_login_headers(client, staff_a["email"], staff_a["password"])

    response = await client.patch(
        f"/v1/users/admin/update/{staff_b['id']}",
        json={"name": "Hacked"},
        headers=staff_a_headers
    )
    assert response.status_code == 403


# ==========================================
# DELETE /v1/users/{id}
# ==========================================

@pytest.mark.asyncio
async def test_delete_user_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])

    with (
        patch.object(user_service, "search_user_by_id", new=search_user_as_dict),
        patch.object(users_route, "search_user_by_id", new=search_user_as_dict),
    ):
        response = await client.delete(
            f"/v1/users/{staff['id']}",
            headers=data["owner_headers"]
        )
    assert response.status_code == 200
    assert "deactivated" in response.json()["message"]


@pytest.mark.asyncio
async def test_delete_user_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.delete("/v1/users/99999", headers=root_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_no_token_returns_401(client):
    response = await client.delete("/v1/users/1")
    assert response.status_code == 401