"""
Integration tests for /v1/organizations routes.
"""

import pytest

from tests.conftest import (
    api_create_org,
    api_create_staff,
    api_login_headers,
    api_register_root,
    setup_org_with_owner,
    unique_name,
    unique_slug,
)

# ==========================================
# POST /v1/organizations
# ==========================================

@pytest.mark.asyncio
async def test_create_organization_as_root_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.post("/v1/organizations", json={
        "name": unique_name("Clinic"),
        "slug": unique_slug(),
        "min_work_time": "08:00:00",
        "max_work_time": "18:00:00"
    }, headers=root_headers)
    assert response.status_code == 201
    assert "OrgID" in response.json()["message"]


@pytest.mark.asyncio
async def test_create_organization_as_owner_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.post("/v1/organizations", json={
        "name": unique_name("Illegal"),
        "slug": unique_slug(),
        "min_work_time": "08:00:00",
        "max_work_time": "18:00:00"
    }, headers=data["owner_headers"])
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_organization_no_token_returns_401(client):
    response = await client.post("/v1/organizations", json={
        "name": unique_name("Ghost"),
        "slug": unique_slug(),
        "min_work_time": "08:00:00",
        "max_work_time": "18:00:00"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_organization_invalid_work_time_returns_422(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.post("/v1/organizations", json={
        "name": unique_name("Bad"),
        "slug": unique_slug(),
        "min_work_time": "18:00:00",
        "max_work_time": "08:00:00"  # inverted — Pydantic must reject
    }, headers=root_headers)
    assert response.status_code == 422


# ==========================================
# GET /v1/organizations/{id}
# ==========================================

@pytest.mark.asyncio
async def test_get_organization_as_owner_returns_200(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.get(f"/v1/organizations/{data['org']['id']}", headers=data["owner_headers"])
    assert response.status_code == 200
    assert response.json()["id"] == data["org"]["id"]


@pytest.mark.asyncio
async def test_get_organization_as_root_returns_200(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    org = await api_create_org(client, root_headers)

    response = await client.get(f"/v1/organizations/{org['id']}", headers=root_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_organization_as_staff_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_headers = await api_login_headers(client, staff["email"], staff["password"])

    response = await client.get(f"/v1/organizations/{data['org']['id']}", headers=staff_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_organization_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.get("/v1/organizations/99999", headers=root_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_organization_no_token_returns_401(client):
    response = await client.get("/v1/organizations/1")
    assert response.status_code == 401


# ==========================================
# PATCH /v1/organizations/{id}
# ==========================================

@pytest.mark.asyncio
async def test_update_organization_as_owner_success(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.patch(
        f"/v1/organizations/{data['org']['id']}",
        json={"name": unique_name("Updated")},
        headers=data["owner_headers"]
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_organization_as_staff_returns_403(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)
    staff = await api_create_staff(client, data["owner_headers"], data["org"]["id"])
    staff_headers = await api_login_headers(client, staff["email"], staff["password"])

    response = await client.patch(
        f"/v1/organizations/{data['org']['id']}",
        json={"name": "Hacked"},
        headers=staff_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_organization_not_found_returns_404(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])

    response = await client.patch("/v1/organizations/99999", json={"name": "Ghost"}, headers=root_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_organization_no_token_returns_401(client):
    response = await client.patch("/v1/organizations/1", json={"name": "X"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_organization_owner_of_different_org_returns_403(client):
    """Owner of org A must not be able to update org B."""
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data_a = await setup_org_with_owner(client, root_headers)
    org_b = await api_create_org(client, root_headers)

    response = await client.patch(
        f"/v1/organizations/{org_b['id']}",
        json={"name": "Hijacked"},
        headers=data_a["owner_headers"]
    )
    assert response.status_code == 403


# ==========================================
# GET/PATCH /v1/organizations/{id}/settings
# ==========================================

@pytest.mark.asyncio
async def test_get_organization_settings_returns_defaults(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.get(
        f"/v1/organizations/{data['org']['id']}/settings",
        headers=data["owner_headers"],
    )

    assert response.status_code == 200
    assert response.json()["operating_weekdays"] == [1, 2, 3, 4, 5, 6, 7]
    assert response.json()["cancellation_buffer_hours"] == 24


@pytest.mark.asyncio
async def test_patch_organization_settings_updates_weekdays_and_buffer(client):
    root = await api_register_root(client)
    root_headers = await api_login_headers(client, root["email"], root["password"])
    data = await setup_org_with_owner(client, root_headers)

    response = await client.patch(
        f"/v1/organizations/{data['org']['id']}/settings",
        json={"operating_weekdays": [1, 2, 3, 4, 5], "cancellation_buffer_hours": 48},
        headers=data["owner_headers"],
    )

    assert response.status_code == 200

    settings_response = await client.get(
        f"/v1/organizations/{data['org']['id']}/settings",
        headers=data["owner_headers"],
    )
    assert settings_response.status_code == 200
    assert settings_response.json()["operating_weekdays"] == [1, 2, 3, 4, 5]
    assert settings_response.json()["cancellation_buffer_hours"] == 48