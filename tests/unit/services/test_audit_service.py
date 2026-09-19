"""
Unit tests for audit_service.py

All DB interactions are mocked via AsyncMock on engine.begin() / engine.connect().
Focus: JSON serialization of log values, query filters, IP extraction, sanitization.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.services.audit_service import (
    get_audit_logs,
    get_ip_from_request,
    log_action,
    sanitize_audit_values,
)


def _make_conn(scalar_val=None, mapping_val=None, all_val=None) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.scalar.return_value = scalar_val
    mock_result.mappings.return_value.one_or_none.return_value = mapping_val
    mock_result.mappings.return_value.all.return_value = all_val or []

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    return mock_conn


# ==========================================
# log_action
# ==========================================

@pytest.mark.asyncio
async def test_log_action_returns_id():
    mock_conn = _make_conn(scalar_val=101)

    with patch("app.api.v1.services.audit_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await log_action(
            organization_id=1,
            actor_user_id=10,
            action="CREATE",
            entity_type="CUSTOMER",
            entity_id=5,
            old_values=None,
            new_values={"name": "Alice"},
            metadata={"source": "api"},
            ip_address="127.0.0.1",
        )

    assert result == 101


# ==========================================
# get_audit_logs
# ==========================================

@pytest.mark.asyncio
async def test_get_audit_logs_returns_list():
    rows = [{"id": 1, "action": "CREATE", "entity_type": "CUSTOMER"}]
    mock_conn = _make_conn(all_val=rows)

    with patch("app.api.v1.services.audit_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn

        result = await get_audit_logs(
            limit=10,
            offset=0,
            actor_user_id=10,
            entity_type="CUSTOMER",
            action="CREATE",
        )

    assert isinstance(result, list)
    assert len(result) == 1


# ==========================================
# get_ip_from_request
# ==========================================

def test_get_ip_from_request_from_client():
    request = MagicMock()
    request.client.host = "192.168.1.1"

    ip = get_ip_from_request(request)
    assert ip == "192.168.1.1"


def test_get_ip_from_request_from_forwarded_for():
    request = MagicMock()
    request.client = None
    request.headers.get.return_value = "203.0.113.195, 70.41.3.18"

    ip = get_ip_from_request(request)
    assert ip == "203.0.113.195"


def test_get_ip_from_request_none():
    request = MagicMock()
    request.client = None
    request.headers.get.return_value = None

    ip = get_ip_from_request(request)
    assert ip is None


# ==========================================
# sanitize_audit_values
# ==========================================

def test_sanitize_audit_values_removes_password_hash():
    data = {"name": "Alice", "password_hash": "secret_hash", "role": "STAFF"}
    sanitized = sanitize_audit_values(data)

    assert "password_hash" not in sanitized
    assert sanitized["name"] == "Alice"


def test_sanitize_audit_values_none_returns_none():
    assert sanitize_audit_values(None) is None
