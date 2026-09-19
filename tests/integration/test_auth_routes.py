"""
Integration tests for /v1/register and /v1/login routes.
"""

import pytest

from tests.conftest import api_register_root, unique_email, unique_name

# ==========================================
# POST /v1/register
# ==========================================

@pytest.mark.asyncio
async def test_register_root_or_login_succeeds(client):
    """ROOT is created or reused — either way we get a valid user back."""
    root = await api_register_root(client)
    assert root["id"] > 0
    assert root["role"] == "ROOT"


@pytest.mark.asyncio
async def test_register_second_root_returns_409(client):
    """A second ROOT with a different email must be rejected."""
    await api_register_root(client)

    response = await client.post("/v1/register", json={
        "name": "Another Root",
        "email": unique_email(),
        "password": "rootpass123",
        "role": "ROOT",
        "organization_id": None,
        "is_active": True
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    root = await api_register_root(client)

    response = await client.post("/v1/register", json={
        "name": "Duplicate",
        "email": root["email"],
        "password": "somepass123",
        "role": "ROOT",
        "organization_id": None,
        "is_active": True
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_owner_without_root_token_returns_403(client):
    response = await client.post("/v1/register", json={
        "name": unique_name("Owner"),
        "email": unique_email(),
        "password": "ownerpass123",
        "role": "OWNER",
        "organization_id": None,
        "is_active": True
    })
    assert response.status_code == 403


# ==========================================
# POST /v1/login
# ==========================================

@pytest.mark.asyncio
async def test_login_correct_credentials_returns_token(client):
    root = await api_register_root(client)

    response = await client.post("/v1/login", json={
        "email": root["email"],
        "password": root["password"]
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    root = await api_register_root(client)

    response = await client.post("/v1/login", json={
        "email": root["email"],
        "password": "totally_wrong_password"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_404(client):
    response = await client.post("/v1/login", json={
        "email": unique_email(),
        "password": "doesntmatter"
    })
    assert response.status_code == 404