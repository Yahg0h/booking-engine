"""
All services related to professional management used across Booking Engine routes.
"""

from datetime import datetime, time

from sqlalchemy import text

from app.database import engine


# DATABASE OPERATIONS
async def create_professionals(organization_id: int, user_id: int, name: str, buffer_time_minutes: str, is_active: bool | None) -> int:
    async with engine.begin() as conn:
        create_query = """
        INSERT INTO professionals (organization_id, user_id, name, buffer_time_minutes, is_active)
        VALUES (:organization_id, :user_id, :name, :buffer_time_minutes, :is_active)
        """
        await conn.execute(text(create_query), {"organization_id": organization_id, "user_id": user_id, "name": name,
                                                "buffer_time_minutes": buffer_time_minutes, "is_active": is_active})

        select_query = """
        SELECT id FROM professionals
        WHERE organization_id = :organization_id AND user_id = :user_id
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(select_query), {"organization_id": organization_id, "user_id": user_id})
        recent_pro_id = query.scalar()

    return recent_pro_id

async def search_professional_by_id(id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals WHERE id = :id"), {"id": id})
        pro_dict = query.mappings().one_or_none()

    return pro_dict

async def search_professional_by_user_id(user_id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals WHERE user_id = :user_id"), {"user_id": user_id})
        pro_dict = query.mappings().one_or_none()

    return pro_dict

async def search_professionals_by_name(name: str) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals WHERE name LIKE :name"), {"name": name})
        results = query.mappings().one_or_none()

    return results

async def list_professionals_by_org(organization_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals WHERE organization_id = :organization_id"), {"organization_id": organization_id})
        professionals = query.mappings().all()

        registered_professionals = [dict(pro_dict) for pro_dict in professionals]

    return registered_professionals

async def list_all_professionals() -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals"))
        professionals = query.mappings().all()

        registered_professionals = [dict(pro_dict) for pro_dict in professionals]

    return registered_professionals

async def update_professional(id: int, organization_id: int | None, name: str | None, user_id: int | None, buffer_time_minutes: int | None, is_active: bool | None) -> dict | None:
    async with engine.begin() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"id": id}

        if organization_id is not None:
            updates.append("organization_id = :organization_id")
            params["organization_id"] = organization_id

        if name is not None:
            updates.append("name = :name")
            params["name"] = name

        if user_id is not None:
            updates.append("user_id = :user_id")
            params["user_id"] = user_id

        if buffer_time_minutes is not None:
            updates.append("buffer_time_minutes = :buffer_time_minutes")
            params["buffer_time_minutes"] = buffer_time_minutes

        if is_active is not None:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if not updates:
            return None

        query = f"UPDATE professionals SET {', '.join(updates)} WHERE id = :id"
        
        await conn.execute(text(query), params)

        retrieve_query = await conn.execute(text("SELECT * FROM professionals WHERE id = :id"), {"id": id})
        updated_pro = retrieve_query.mappings().one_or_none()

    return updated_pro

async def change_is_active(id: int, is_active: bool) -> bool:
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE professionals SET is_active = :is_active WHERE id = :id"), {"is_active": is_active, "id": id})

    return True

# WORKING HOURS related services

async def create_working_hours(professional_id: int, weekday: int, start_time: time, end_time: time, is_active: bool) -> int | None:
    async with engine.begin() as conn:
        create_query = """
        INSERT INTO working_hours (professional_id, weekday, start_time, end_time, is_active)
        VALUES (:professional_id, :weekday, :start_time, :end_time, :is_active)
        """
        await conn.execute(text(create_query), {"professional_id": professional_id, "weekday": weekday, "start_time": start_time,
                                                "end_time": end_time, "is_active": is_active})

        select_query = """
        SELECT id FROM working_hours
        WHERE professional_id = :professional_id
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(select_query), {"professional_id": professional_id})
        working_hour_id = query.scalar()

    return working_hour_id

async def search_working_hour_by_id(id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM working_hours WHERE id = :id"), {"id": id})
        working_hour = query.mappings().one_or_none()

    return working_hour

async def list_working_hours_by_professional(professional_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM working_hours WHERE professional_id = :professional_id"), {"professional_id": professional_id})
        results = query.mappings().all()

        registered_wks = [dict(wk_row) for wk_row in results]

    return registered_wks

async def list_all_working_hours() -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM working_hours"))
        results = query.mappings().all()

        registered_wks = [dict(wk_row) for wk_row in results]

    return registered_wks

async def update_working_hours(id: int, weekday: int | None, start_time: time | None, end_time: time | None, is_active: bool | None) -> dict | None:
    async with engine.begin() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"id": id}

        if weekday is not None:
            updates.append("weekday = :weekday")
            params["weekday"] = weekday

        if start_time is not None:
            updates.append("start_time = :start_time")
            params["start_time"] = start_time

        if end_time is not None:
            updates.append("end_time = :end_time")
            params["end_time"] = end_time

        if is_active is not None:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if not updates:
            return None

        query = f"UPDATE working_hours SET {', '.join(updates)} WHERE id = :id"
                
        await conn.execute(text(query), params)

        retrieve_query = await conn.execute(text("SELECT * FROM working_hours WHERE id = :id"), {"id": id})
        recent_wk = retrieve_query.mappings().one_or_none()

    return recent_wk

# BUFFER TIME changes (owner-only)

async def change_buffer_time(id: int, buffer_time_minutes: int) -> dict | None:
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE professionals SET buffer_time_minutes = :buffer_time_minutes WHERE id = :id"),
                           {"buffer_time_minutes": buffer_time_minutes, "id": id})

        query = await conn.execute(text("SELECT * FROM professionals WHERE id = :id"), {"id": id})
        updated_info = query.mappings().one_or_none()

    return updated_info

# BLACKOUTS related services (professionals only)

async def create_blackouts(professional_id: int, start_at: datetime, end_at: datetime, reason: str) -> int:
    async with engine.begin() as conn:
        create_query = """
        INSERT INTO blackouts (professional_id, start_at, end_at, reason)
        VALUES (:professional_id, :start_at, :end_at, :reason)
        """
        await conn.execute(text(create_query), {"professional_id": professional_id, "start_at": start_at, "end_at": end_at, "reason": reason})

        select_query = """
        SELECT id FROM blackouts
        WHERE professional_id = :professional_id
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(select_query), {"professional_id": professional_id})
        recent_blackout_id = query.scalar()

    return recent_blackout_id

async def search_blackout_by_id(id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM blackouts WHERE id = :id"), {"id": id})
        blackout = query.mappings().one_or_none()

    return blackout

async def list_blackouts_by_professional(professional_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM blackouts WHERE professional_id = :professional_id"), {"professional_id": professional_id})
        results = query.mappings().all()

        registered_blackouts = [dict(blackout_dict) for blackout_dict in results]

    return registered_blackouts

async def update_blackout(id: int, professional_id: int, start_at: datetime | None, end_at: datetime | None, reason: str | None) -> dict | None:
    async with engine.begin() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"id": id}

        # Add professional id to the search
        updates.append("professional_id = :professional_id")
        params["professional_id"] = professional_id

        # Optionals
        if start_at is not None:
            updates.append("start_at = :start_at")
            params["start_at"] = start_at

        if end_at is not None:
            updates.append("end_at = :end_at")
            params["end_at"] = end_at

        if reason is not None:
            updates.append("reason = :reason")
            params["reason"] = reason

        if not updates:
            return None

        query = f"UPDATE blackouts SET {', '.join(updates)} WHERE id = :id"
                        
        await conn.execute(text(query), params)

        retrieve_query = await conn.execute(text("SELECT * FROM blackouts WHERE id = :id"), {"id": id})
        recent_blackout = retrieve_query.mappings().one_or_none()

    return recent_blackout
