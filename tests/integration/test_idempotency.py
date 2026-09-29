"""
Integration tests for IdempotencyMiddleware.

Requests use a minimal ASGI app while authentication and Redis operations are mocked.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import Response

from app.api.v1.middleware import idempotency as idempotency_module
from app.api.v1.middleware.idempotency import IdempotencyMiddleware


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)
    app.state.endpoint_calls = 0

    @app.post("/v1/appointments")
    async def create_appointment():
        app.state.endpoint_calls += 1
        return {"created": True}

    async def track_request():
        app.state.endpoint_calls += 1
        return {"created": True}

    for method, path in [
        ("POST", "/v1/customers"),
        ("POST", "/v1/professionals/{professional_id}/blackouts"),
        ("POST", "/v1/professionals/{professional_id}/procedures"),
        ("PATCH", "/v1/appointments/{appointment_id}"),
        ("PATCH", "/v1/customers/{customer_id}"),
        ("PATCH", "/v1/organizations/{organization_id}/settings"),
        ("POST", "/v1/professionals/not-a-number/blackouts"),
    ]:
        app.add_api_route(path, track_request, methods=[method])

    @app.post("/v1/other")
    async def create_other_resource():
        app.state.endpoint_calls += 1
        return {"created": True}

    @app.get("/v1/appointments")
    async def get_appointments():
        app.state.endpoint_calls += 1
        return {"method": "GET"}

    @app.post("/v1/plain-response")
    async def create_plain_response():
        app.state.endpoint_calls += 1
        return Response(content="created", media_type="text/plain")

    return app


def _mock_idempotency_dependencies(monkeypatch, cached_result=(False, None)):
    redis_client = Mock()
    decode_token = Mock(return_value=17)
    search_user_by_id = AsyncMock(return_value={"organization_id": 9})
    check_idempotent_request = AsyncMock(return_value=cached_result)
    store_response = AsyncMock()

    monkeypatch.setattr(idempotency_module, "redis_client", redis_client)
    monkeypatch.setattr(idempotency_module, "decode_token", decode_token)
    monkeypatch.setattr(idempotency_module, "search_user_by_id", search_user_by_id)
    monkeypatch.setattr(idempotency_module, "check_idempotent_request", check_idempotent_request)
    monkeypatch.setattr(idempotency_module, "store_response", store_response)

    return redis_client, decode_token, search_user_by_id, check_idempotent_request, store_response


async def _request(app, method: str, path: str, headers: dict | None = None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("POST", "/v1/appointments"),
    ("POST", "/v1/customers"),
    ("POST", "/v1/professionals/12/blackouts"),
    ("POST", "/v1/professionals/12/procedures"),
    ("PATCH", "/v1/appointments/12"),
    ("PATCH", "/v1/customers/12"),
    ("PATCH", "/v1/organizations/12/settings"),
])
async def test_critical_route_without_idempotency_key_returns_400(monkeypatch, method, path):
    app = _create_test_app()
    _mock_idempotency_dependencies(monkeypatch)

    response = await _request(app, method, path)

    assert response.status_code == 400
    assert response.json() == {"error": "Idempotent-Key header is required for this operation"}
    assert app.state.endpoint_calls == 0


@pytest.mark.asyncio
async def test_critical_pattern_does_not_match_non_numeric_id(monkeypatch):
    app = _create_test_app()
    _, _, _, check_idempotent_request, store_response = _mock_idempotency_dependencies(monkeypatch)

    response = await _request(app, "POST", "/v1/professionals/not-a-number/blackouts")

    assert response.status_code == 200
    assert response.json() == {"created": True}
    assert app.state.endpoint_calls == 1
    check_idempotent_request.assert_not_awaited()
    store_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_critical_post_without_key_reaches_endpoint(monkeypatch):
    app = _create_test_app()
    _, _, _, check_idempotent_request, store_response = _mock_idempotency_dependencies(monkeypatch)

    response = await _request(app, "POST", "/v1/other")

    assert response.status_code == 200
    assert response.json() == {"created": True}
    assert app.state.endpoint_calls == 1
    check_idempotent_request.assert_not_awaited()
    store_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_with_key_and_missing_authorization_returns_401(monkeypatch):
    app = _create_test_app()
    _, decode_token, _, check_idempotent_request, _ = _mock_idempotency_dependencies(monkeypatch)

    response = await _request(app, "POST", "/v1/other", headers={"Idempotent-Key": "request-1"})

    assert response.status_code == 401
    assert response.json() == {"error": "Missing Authorization header"}
    assert app.state.endpoint_calls == 0
    decode_token.assert_not_called()
    check_idempotent_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_response_is_returned_without_calling_endpoint(monkeypatch):
    app = _create_test_app()
    redis_client, _, _, check_idempotent_request, store_response = _mock_idempotency_dependencies(
        monkeypatch,
        cached_result=(True, {"status_code": 201, "body": {"created": True}}),
    )
    headers = {
        "Authorization": "Bearer valid-token",
        "Idempotent-Key": "request-2",
    }

    response = await _request(app, "POST", "/v1/other", headers=headers)

    assert response.status_code == 201
    assert response.json() == {"created": True}
    assert app.state.endpoint_calls == 0
    check_idempotent_request.assert_awaited_once_with(redis_client, 9, "request-2")
    store_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_miss_runs_endpoint_and_stores_response(monkeypatch):
    app = _create_test_app()
    redis_client, decode_token, search_user_by_id, check_idempotent_request, store_response = (
        _mock_idempotency_dependencies(monkeypatch)
    )
    headers = {
        "Authorization": "Bearer valid-token",
        "Idempotent-Key": "request-3",
    }

    response = await _request(app, "POST", "/v1/other", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"created": True}
    assert app.state.endpoint_calls == 1
    decode_token.assert_called_once_with("valid-token")
    search_user_by_id.assert_awaited_once_with(17)
    check_idempotent_request.assert_awaited_once_with(redis_client, 9, "request-3")
    store_response.assert_awaited_once_with(redis_client, 9, "request-3", 200, {"created": True})


@pytest.mark.asyncio
async def test_cache_check_failure_still_runs_endpoint_and_stores_response(monkeypatch):
    app = _create_test_app()
    redis_client, _, _, check_idempotent_request, store_response = _mock_idempotency_dependencies(monkeypatch)
    check_idempotent_request.side_effect = RuntimeError("Redis unavailable")
    headers = {
        "Authorization": "Bearer valid-token",
        "Idempotent-Key": "request-4",
    }

    response = await _request(app, "POST", "/v1/other", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"created": True}
    assert app.state.endpoint_calls == 1
    store_response.assert_awaited_once_with(redis_client, 9, "request-4", 200, {"created": True})


@pytest.mark.asyncio
async def test_store_failure_does_not_change_endpoint_response(monkeypatch):
    app = _create_test_app()
    _, _, _, _, store_response = _mock_idempotency_dependencies(monkeypatch)
    store_response.side_effect = RuntimeError("Redis unavailable")
    headers = {
        "Authorization": "Bearer valid-token",
        "Idempotent-Key": "request-5",
    }

    response = await _request(app, "POST", "/v1/other", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"created": True}
    assert app.state.endpoint_calls == 1


@pytest.mark.asyncio
async def test_non_json_response_is_preserved_and_fallback_is_cached(monkeypatch):
    app = _create_test_app()
    redis_client, _, _, _, store_response = _mock_idempotency_dependencies(monkeypatch)
    headers = {
        "Authorization": "Bearer valid-token",
        "Idempotent-Key": "request-6",
    }

    response = await _request(app, "POST", "/v1/plain-response", headers=headers)

    assert response.status_code == 200
    assert response.text == "created"
    assert app.state.endpoint_calls == 1
    store_response.assert_awaited_once_with(
        redis_client,
        9,
        "request-6",
        200,
        {"error": "invalid response"},
    )