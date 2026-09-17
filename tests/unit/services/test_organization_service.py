"""
Unit tests for organization_service.py

Focus: update_organization empty-fields guard, check_organization_access logic.
"""

from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.services.organization_service import (
    check_organization_access,
    update_organization,
)

# ==========================================
# update_organization
# ==========================================

@pytest.mark.asyncio
async def test_update_organization_no_fields_returns_none():
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.organization_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_organization(
            organization_id=1,
            name=None,
            slug=None,
            min_work_time=None,
            max_work_time=None
        )
    assert result is None


@pytest.mark.asyncio
async def test_update_organization_with_fields_executes_update():
    fake_org = {
        "id": 1, "name": "Updated Org", "slug": "updated-org",
        "min_work_time": time(8, 0), "max_work_time": time(18, 0)
    }

    mock_result = MagicMock()
    mock_result.mappings.return_value.one_or_none.return_value = fake_org

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.v1.services.organization_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_conn

        result = await update_organization(
            organization_id=1,
            name="Updated Org",
            slug=None,
            min_work_time=None,
            max_work_time=None
        )

    assert mock_conn.execute.call_count == 2  # UPDATE + SELECT
    assert result["name"] == "Updated Org"


# ==========================================
# check_organization_access
# ==========================================

@pytest.mark.asyncio
async def test_check_organization_access_root_returns_true():
    with patch("app.api.v1.services.organization_service.is_root",
               new=AsyncMock(return_value=True)):
        with patch("app.api.v1.services.organization_service.is_owner",
                   new=AsyncMock(return_value=False)):
            result = await check_organization_access(user_id=1, organization_id=1)
    assert result is True


@pytest.mark.asyncio
async def test_check_organization_access_owner_returns_true():
    with patch("app.api.v1.services.organization_service.is_root",
               new=AsyncMock(return_value=False)):
        with patch("app.api.v1.services.organization_service.is_owner",
                   new=AsyncMock(return_value=True)):
            result = await check_organization_access(user_id=2, organization_id=1)
    assert result is True


@pytest.mark.asyncio
async def test_check_organization_access_staff_returns_false():
    with patch("app.api.v1.services.organization_service.is_root",
               new=AsyncMock(return_value=False)):
        with patch("app.api.v1.services.organization_service.is_owner",
                   new=AsyncMock(return_value=False)):
            result = await check_organization_access(user_id=3, organization_id=1)
    assert result is False