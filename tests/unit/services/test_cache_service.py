"""Unit tests for cache serialization and the cached decorator."""

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest
from starlette.requests import Request

from app.api.v1.services import cache_service


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2025, 1, 2), "2025-01-02"),
        (datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc), "2025-01-02T03:04:00+00:00"),
        (pd.Timestamp("2025-01-02T03:04:00Z"), "2025-01-02T03:04:00+00:00"),
        (Decimal("12.50"), 12.5),
        (pd.DataFrame([{"id": 1, "name": "A"}]), [{"id": 1, "name": "A"}]),
        (pd.Series([1, 2]), [1, 2]),
    ],
)
def test_json_serializer_handles_supported_types(value, expected):
    serialized = cache_service.json_serializer(value)

    if isinstance(expected, str):
        assert serialized == expected
    else:
        assert serialized == expected


def test_json_serializer_rejects_unsupported_type():
    with pytest.raises(TypeError, match="not JSON serializable"):
        cache_service.json_serializer(object())


def test_get_cached_returns_decoded_json(monkeypatch):
    redis_client = Mock()
    redis_client.get.return_value = '{"ready": true, "count": 3}'
    monkeypatch.setattr(cache_service, "redis_client", redis_client)

    assert cache_service.get_cached("cache:key") == {"ready": True, "count": 3}
    redis_client.get.assert_called_once_with("cache:key")


def test_get_cached_returns_none_for_missing_or_invalid_json(monkeypatch):
    redis_client = Mock()
    redis_client.get.side_effect = [None, "not-json"]
    monkeypatch.setattr(cache_service, "redis_client", redis_client)

    assert cache_service.get_cached("cache:missing") is None
    assert cache_service.get_cached("cache:invalid") is None


def test_set_cached_serializes_dates_decimal_and_dataframe(monkeypatch):
    redis_client = Mock()
    monkeypatch.setattr(cache_service, "redis_client", redis_client)
    value = {
        "created_at": datetime(2025, 1, 2, tzinfo=timezone.utc),
        "price": Decimal("19.95"),
        "rows": pd.DataFrame([{"id": 5}]),
    }

    cache_service.set_cached("cache:report", value, ttl=120)

    redis_client.set.assert_called_once()
    key, serialized = redis_client.set.call_args.args
    assert key == "cache:report"
    assert json.loads(serialized) == {
        "created_at": "2025-01-02T00:00:00+00:00",
        "price": 19.95,
        "rows": [{"id": 5}],
    }
    assert redis_client.set.call_args.kwargs == {"ex": 120}


def _request() -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/test",
        "raw_path": b"/test",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 8000),
        "server": ("test", 80),
    })


@pytest.mark.asyncio
async def test_cached_decorator_omits_request_but_keeps_user_id_in_cache_key(monkeypatch):
    get_cached = Mock(return_value=None)
    set_cached = Mock()
    monkeypatch.setattr(cache_service, "get_cached", get_cached)
    monkeypatch.setattr(cache_service, "set_cached", set_cached)
    endpoint = AsyncMock(return_value={"result": "fresh"})
    endpoint.__name__ = "report_endpoint"
    decorated_endpoint = cache_service.cached(ttl=45)(endpoint)
    request = _request()
    date_filter = date(2025, 3, 4)

    result = await decorated_endpoint(
        request=request,
        organization_id=6,
        date_filter=date_filter,
        user_id=19,
    )

    expected_key = "cache:report_endpoint:{'organization_id': 6, 'date_filter': '2025-03-04', 'user_id': 19}"
    assert result == {"result": "fresh"}
    endpoint.assert_awaited_once()
    get_cached.assert_called_once_with(expected_key)
    set_cached.assert_called_once_with(expected_key, {"result": "fresh"}, 45)


@pytest.mark.asyncio
async def test_cached_decorator_uses_distinct_keys_for_different_users(monkeypatch):
    get_cached = Mock(return_value=None)
    set_cached = Mock()
    monkeypatch.setattr(cache_service, "get_cached", get_cached)
    monkeypatch.setattr(cache_service, "set_cached", set_cached)
    endpoint = AsyncMock(side_effect=[{"user_id": 19}, {"user_id": 20}])
    endpoint.__name__ = "user_scoped_endpoint"
    decorated_endpoint = cache_service.cached(ttl=45)(endpoint)

    first = await decorated_endpoint(organization_id=6, user_id=19)
    second = await decorated_endpoint(organization_id=6, user_id=20)

    assert first == {"user_id": 19}
    assert second == {"user_id": 20}
    first_key = get_cached.call_args_list[0].args[0]
    second_key = get_cached.call_args_list[1].args[0]
    assert first_key != second_key
    assert "'user_id': 19" in first_key
    assert "'user_id': 20" in second_key


@pytest.mark.asyncio
async def test_cached_decorator_returns_cache_hit_without_calling_endpoint(monkeypatch):
    get_cached = Mock(return_value={"result": "cached"})
    set_cached = Mock()
    monkeypatch.setattr(cache_service, "get_cached", get_cached)
    monkeypatch.setattr(cache_service, "set_cached", set_cached)
    endpoint = AsyncMock(return_value={"result": "fresh"})
    decorated_endpoint = cache_service.cached(ttl=45)(endpoint)

    result = await decorated_endpoint(organization_id=6)

    assert result == {"result": "cached"}
    endpoint.assert_not_awaited()
    set_cached.assert_not_called()
