"""
Unit tests for organization_settings_service.py.

Focus: default settings creation, JSON normalization, and partial updates.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.services.organization_settings_service import (
    create_organization_settings,
    get_organization_settings,
    update_organization_settings,
)


def make_async_connection(result=None):
    mock_connection = AsyncMock()
    mock_connection.execute = AsyncMock(return_value=result)
    mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
    mock_connection.__aexit__ = AsyncMock(return_value=False)
    return mock_connection


# ==========================================
# create_organization_settings
# ==========================================

@pytest.mark.asyncio
async def test_create_organization_settings_uses_defaults():
    """
    Verifies that organization settings are created with the default values.

    Returns:
        None: The test passes when the service returns True and persists the expected defaults
    """
    mock_connection = make_async_connection()

    with patch("app.api.v1.services.organization_settings_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_connection

        result = await create_organization_settings(org_id=7)

    assert result is True
    mock_connection.execute.assert_awaited_once()
    parameters = mock_connection.execute.await_args.args[1]
    assert parameters == {
        "organization_id": 7,
        "operating_weekdays": "[1, 2, 3, 4, 5, 6, 7]",
        "cancellation_buffer_hours": 24,
    }


# ==========================================
# get_organization_settings
# ==========================================

@pytest.mark.asyncio
async def test_get_organization_settings_decodes_json_weekdays():
    """
    Verifies that stored operating weekdays are decoded from JSON into a list.

    Returns:
        None: The test passes when the service returns normalized organization settings
    """
    mock_result = MagicMock()
    mock_result.mappings.return_value.one_or_none.return_value = {
        "organization_id": 7,
        "operating_weekdays": "[1, 2, 5]",
        "cancellation_buffer_hours": 24,
    }
    mock_connection = make_async_connection(mock_result)

    with patch("app.api.v1.services.organization_settings_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_connection

        result = await get_organization_settings(org_id=7)

    assert result == {
        "organization_id": 7,
        "operating_weekdays": [1, 2, 5],
        "cancellation_buffer_hours": 24,
    }


@pytest.mark.asyncio
async def test_get_organization_settings_returns_none_when_missing():
    """
    Verifies that missing organization settings return None.

    Returns:
        None: The test passes when the service returns None for an unknown organization
    """
    mock_result = MagicMock()
    mock_result.mappings.return_value.one_or_none.return_value = None
    mock_connection = make_async_connection(mock_result)

    with patch("app.api.v1.services.organization_settings_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_connection

        result = await get_organization_settings(org_id=999)

    assert result is None


# ==========================================
# update_organization_settings
# ==========================================

@pytest.mark.asyncio
async def test_update_organization_settings_without_fields_returns_none():
    """
    Verifies that an update without fields does not execute a database query.

    Returns:
        None: The test passes when the service returns None without updating the database
    """
    mock_connection = make_async_connection()

    with patch("app.api.v1.services.organization_settings_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_connection

        result = await update_organization_settings(
            org_id=7,
            operating_weekdays=None,
            cancellation_buffer_hours=None,
        )

    assert result is None
    mock_connection.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_organization_settings_updates_selected_fields():
    """
    Verifies that selected organization settings are serialized and persisted.

    Returns:
        None: The test passes when the expected fields are updated and returned
    """
    fake_settings = {
        "organization_id": 7,
        "operating_weekdays": "[1, 3, 5]",
        "cancellation_buffer_hours": 12,
    }
    mock_result = MagicMock()
    mock_result.mappings.return_value.one_or_none.return_value = fake_settings
    mock_connection = make_async_connection(mock_result)

    with patch("app.api.v1.services.organization_settings_service.engine") as mock_engine:
        mock_engine.begin.return_value = mock_connection

        result = await update_organization_settings(
            org_id=7,
            operating_weekdays=[1, 3, 5],
            cancellation_buffer_hours=12,
        )

    assert mock_connection.execute.await_count == 2
    update_parameters = mock_connection.execute.await_args_list[0].args[1]
    assert update_parameters == {
        "organization_id": 7,
        "operating_weekdays": "[1, 3, 5]",
        "cancellation_buffer_hours": 12,
    }
    assert result == fake_settings
