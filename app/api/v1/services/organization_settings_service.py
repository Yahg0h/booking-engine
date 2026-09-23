"""
All services related to organization settings management used across Booking Engine routes.
"""

import json

from sqlalchemy import text

from app.database import engine


async def create_organization_settings(org_id: int) -> bool | None:
    # Add default values to organization settings
    # Operating Weekdays (1 = Sunday ... 7 = Saturday)
    operating_weekdays = json.dumps([1,2,3,4,5,6,7])
    cancellation_buffer_hours = 24

    async with engine.begin() as conn:
        create_query = """
        INSERT INTO organization_settings (organization_id, operating_weekdays, cancellation_buffer_hours)
        VALUES (:organization_id, :operating_weekdays, :cancellation_buffer_hours)
        """
        await conn.execute(text(create_query), {"organization_id": org_id, "operating_weekdays": operating_weekdays, "cancellation_buffer_hours": cancellation_buffer_hours})

    return True

async def get_organization_settings(org_id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM organization_settings WHERE organization_id = :organization_id"), {"organization_id": org_id})
        results = query.mappings().one_or_none()

    if results is None:
        return None

    settings = dict(results)
    if isinstance(settings["operating_weekdays"], str):
        settings["operating_weekdays"] = json.loads(settings["operating_weekdays"])

    return settings

async def update_organization_settings(org_id: int, operating_weekdays: list[int] | None, cancellation_buffer_hours: int | None) -> dict | None:
    async with engine.begin() as conn:
        updates = []
        params = {"organization_id": org_id}

        if operating_weekdays is not None:
            updates.append("operating_weekdays = :operating_weekdays")
            params["operating_weekdays"] = json.dumps(operating_weekdays)

        if cancellation_buffer_hours is not None:
            updates.append("cancellation_buffer_hours = :cancellation_buffer_hours")
            params["cancellation_buffer_hours"] = cancellation_buffer_hours

        if not updates:
            return None

        query = f"UPDATE organization_settings SET {', '.join(updates)} WHERE organization_id = :organization_id"

        await conn.execute(text(query), params)

        retrieve_query = await conn.execute(text("SELECT * FROM organization_settings WHERE organization_id = :organization_id"), {"organization_id": org_id})
        updated_org_settings = retrieve_query.mappings().one_or_none()

    return updated_org_settings

