"""
Global test fixtures for BookingEngine test suite.

Unit tests: mock the engine directly.
Integration tests: function-scoped client (um por teste).
Engine leak resolvido com pool_size=1 + NullPool no app durante testes.
"""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool

from app.api.v1.services.auth_service import create_jwt_token

ROOT_EMAIL = "root_test_fixed@bookingengine.com"
ROOT_PASS  = "rootpass_fixed_123"


# ==========================================
# UNIQUE VALUE GENERATORS
# ==========================================

def unique_email() -> str:
    return f"user_{uuid.uuid4().hex[:12]}@example.com"


def unique_slug() -> str:
    return f"org-{uuid.uuid4().hex[:8]}"


def unique_name(prefix: str = "Test") -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


# ==========================================
# TOKEN HELPERS (unit tests only)
# ==========================================

def make_token(user_id: int) -> str:
    return create_jwt_token(user_id)


def auth_headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


# ==========================================
# CLIENT FIXTURE
# Usa NullPool no engine do app durante testes:
# cada conexão é aberta e fechada imediatamente,
# sem pool para vazar entre testes.
# ==========================================

@pytest_asyncio.fixture
async def client():
    from sqlalchemy.ext.asyncio import create_async_engine

    import app.database as db_module
    from app.database import DATABASE_URL

    # Substitui o engine do app por um com NullPool
    test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    original_engine = db_module.engine
    db_module.engine = test_engine

    # Também precisa substituir nos services que importam engine diretamente
    import app.api.v1.services.audit_service as audit_svc
    import app.api.v1.services.organization_service as org_svc
    import app.api.v1.services.permission_service as perm_svc
    import app.api.v1.services.user_service as user_svc

    svc_modules = [user_svc, org_svc, perm_svc, audit_svc]
    for module in svc_modules:
        if hasattr(module, 'engine'):
            module.engine = test_engine

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Restaura engine original e fecha o de teste
    db_module.engine = original_engine
    for module in svc_modules:
        if hasattr(module, 'engine'):
            module.engine = original_engine

    await test_engine.dispose()


# ==========================================
# ROOT HELPER
# ==========================================

async def api_register_root(client) -> dict:
    """
    Garante que ROOT existe com credenciais fixas.
    Login 200  → reutiliza.
    Login 404  → registra.
    Login 401  → ROOT existe com senha diferente (deletar manualmente).
    Reg   409  → ROOT existe com email diferente (deletar manualmente).
    """
    import jwt

    from app.config import settings

    login_resp = await client.post("/v1/login", json={"email": ROOT_EMAIL, "password": ROOT_PASS})

    if login_resp.status_code == 200:
        token = login_resp.json()["access_token"]
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        user_id = int(payload["sub"])
        return {"id": user_id, "email": ROOT_EMAIL, "password": ROOT_PASS,
                "role": "ROOT", "organization_id": None}

    if login_resp.status_code == 404:
        reg_resp = await client.post("/v1/register", json={
            "name": "Test Root Admin",
            "email": ROOT_EMAIL,
            "password": ROOT_PASS,
            "role": "ROOT",
            "organization_id": None,
            "is_active": True
        })
        if reg_resp.status_code == 409:
            raise RuntimeError(
                "ROOT com email diferente já existe. "
                "Execute: DELETE FROM users WHERE role='ROOT';"
            )
        assert reg_resp.status_code == 201, f"Root registration failed: {reg_resp.text}"
        msg = reg_resp.json()["message"]
        user_id = int(msg.split("UserID = ")[1].split(",")[0].rstrip("."))
        return {"id": user_id, "email": ROOT_EMAIL, "password": ROOT_PASS,
                "role": "ROOT", "organization_id": None}

    raise RuntimeError(
        f"Login retornou {login_resp.status_code}: {login_resp.text}\n"
        f"Se 401: ROOT existe com senha diferente. "
        f"Execute: DELETE FROM users WHERE role='ROOT';"
    )


# ==========================================
# REUSABLE API HELPERS
# ==========================================

async def api_login_headers(client, email: str, password: str) -> dict:
    resp = await client.post("/v1/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def api_create_org(client, root_headers: dict, **overrides) -> dict:
    payload = {
        "name": unique_name("Org"),
        "slug": unique_slug(),
        "min_work_time": "08:00:00",
        "max_work_time": "18:00:00",
        **overrides
    }
    resp = await client.post("/v1/organizations", json=payload, headers=root_headers)
    assert resp.status_code == 201, f"Org creation failed: {resp.text}"
    org_id = int(resp.json()["message"].split("OrgID = ")[1].rstrip("."))
    return {"id": org_id, **payload}


async def api_create_owner(client, root_headers: dict, org_id: int,
                            password: str = "testpass123") -> dict:
    payload = {
        "name": unique_name("Owner"),
        "email": unique_email(),
        "password": password,
        "role": "OWNER",
        "organization_id": org_id,
        "is_active": True
    }
    resp = await client.post("/v1/users/owners", json=payload, headers=root_headers)
    assert resp.status_code == 201, f"Owner creation failed: {resp.text}"
    user_id = int(resp.json()["message"].split("UserID = ")[1].split(",")[0].rstrip("."))
    return {"id": user_id, "email": payload["email"], "password": password,
            "role": "OWNER", "organization_id": org_id}


async def api_create_staff(client, owner_headers: dict, org_id: int,
                            password: str = "testpass123") -> dict:
    payload = {
        "name": unique_name("Staff"),
        "email": unique_email(),
        "password": password,
        "role": "STAFF",
        "organization_id": org_id,
        "is_active": True
    }
    resp = await client.post("/v1/users", json=payload, headers=owner_headers)
    assert resp.status_code == 201, f"Staff creation failed: {resp.text}"
    user_id = int(resp.json()["message"].split("UserID = ")[1].split(",")[0].rstrip("."))
    return {"id": user_id, "email": payload["email"], "password": password,
            "role": "STAFF", "organization_id": org_id}


async def setup_org_with_owner(client, root_headers: dict) -> dict:
    org = await api_create_org(client, root_headers)
    owner = await api_create_owner(client, root_headers, org["id"])
    owner_headers = await api_login_headers(client, owner["email"], owner["password"])
    return {"org": org, "owner": owner, "owner_headers": owner_headers}


# ==========================================
# CLEANUP FIXTURE
# ==========================================

@pytest_asyncio.fixture(autouse=True)
async def cleanup_pool_after_test():
    """
    Força cleanup de conexões após cada teste.
    Resolve conflitos de dupla-conexão em operações UPDATE
    que abrem uma tx e depois chamam search_* que abre outra.
    """
    yield
    import app.database as db_module
    if hasattr(db_module.engine, 'dispose'):
        await db_module.engine.dispose()