"""
Unit tests for idempotency_service.py.

Focus: Redis key construction, cached response decoding, and response storage.
"""

import json
from unittest.mock import Mock

import pytest

from app.api.v1.services.idempotency_service import (
    check_idempotent_request,
    store_response,
)


@pytest.mark.asyncio
async def test_check_idempotent_request_returns_cached_response():
    cached_response = {"status_code": 201, "body": {"appointment_id": 42}}
    redis_client = Mock()
    redis_client.get.return_value = json.dumps(cached_response)

    result = await check_idempotent_request(redis_client, org_id=7, idempotency_key="request-1")

    assert result == (True, cached_response)
    redis_client.get.assert_called_once_with("idempotency:7:request-1")


@pytest.mark.asyncio
async def test_check_idempotent_request_returns_miss_when_key_is_absent():
    redis_client = Mock()
    redis_client.get.return_value = None

    result = await check_idempotent_request(redis_client, org_id=7, idempotency_key="request-2")

    assert result == (False, None)
    redis_client.get.assert_called_once_with("idempotency:7:request-2")


@pytest.mark.asyncio
async def test_store_response_serializes_payload_with_five_minute_ttl():
    redis_client = Mock()
    response_body = {"appointment_id": 42}

    result = await store_response(
        redis_client,
        org_id=7,
        idempotency_key="request-3",
        status_code=201,
        response_body=response_body,
    )

    assert result is None
    redis_client.set.assert_called_once_with(
        "idempotency:7:request-3",
        json.dumps({"status_code": 201, "body": response_body}),
        ex=300,
    )


@pytest.mark.asyncio
async def test_check_idempotent_request_propagates_invalid_cached_json():
    redis_client = Mock()
    redis_client.get.return_value = "not-json"

    with pytest.raises(json.JSONDecodeError):
        await check_idempotent_request(redis_client, org_id=7, idempotency_key="request-4")