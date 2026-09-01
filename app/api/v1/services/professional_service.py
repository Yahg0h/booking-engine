"""
All services related to professional management used across Booking Engine routes.
"""

from datetime import time

from sqlalchemy import text

from app.database import engine


# DATABASE OPERATIONS
async def create_professional(organization_id: int, user_id: int | None, name: str, buffer_time_minutes: str, is_active: bool | None) -> int:
    async with engine.connect() as conn:
        create_query = """
        INSERT INTO professionals (organization_id, user_id, name, buffer_time_minutes, is_active)
        VALUES (:organization_id, :user_id, :name, :buffer_time_minutes, :is_active)
        """
        await conn.execute(text(create_query), {"organization_id": organization_id, "user_id": user_id, "name": name,
                                                "buffer_time_minutes": buffer_time_minutes, "is_active": is_active})
        await conn.commit()

        select_query = await conn.execute(text("SELECT id FROM professional WHERE id = LAST_INSERT_ID()"))
        recent_pro_id = select_query.scalar()

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

async def search_organization_by_name(name: str) -> dict | None:
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
    async with engine.connect() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"id": id}

        if organization_id:
            updates.append("organization_id = :organization_id")
            params["organization_id"] = organization_id

        if name:
            updates.append("name = :name")
            params["name"] = name

        if user_id:
            updates.append("user_id = user_id")
            params["user_id"] = name

        if buffer_time_minutes:
            updates.append("buffer_time_minutes = :buffer_time_minutes")
            params["buffer_time_minutes"] = buffer_time_minutes

        if is_active:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if not updates:
            return None

        query = f"UPDATE professionals SET {', '.join(updates)} WHERE id = :id"
        
        await conn.execute(text(query), params)
        await conn.commit()

        retrieve_query = await conn.execute(text("SELECT * FROM professionals WHERE id = :id"), {"id": id})
        updated_pro = retrieve_query.mappings().one_or_none()

    return updated_pro

async def change_is_active(id: int, is_active: bool) -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE professionals SET is_active = :is_active WHERE id: = id"), {"is_active": is_active, "id": id})
        await conn.commit()

    return True

async def create_working_hours(professional_id: int, weekday: int, start_time: time, end_time: time, is_active: bool) -> bool:
    async with engine.connect() as conn:
        create_query = """
        INSERT INTO working_hours (professional_id, weekday, start_time, end_time, is_active)
        VALUES (:professional_id, :weekday, :start_time, :end_time, :is_active)
        """
        await conn.execute(text(create_query), {"professional_id": professional_id, "weekday": weekday, "start_time": start_time,
                                                "end_time": end_time, "is_active": is_active})
        await conn.commit()

    return True

async def update_working_hours(id: int, weekday: int | None, start_time: time | None, end_time: time | None, is_active: bool | None) -> dict | None:
    async with engine.connect() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"id": id}

        if weekday:
            updates.append("weekday = :weekday")
            params["weekday"] = weekday

        if start_time:
            updates.append("start_time = :start_time")
            params["start_time"] = start_time

        if end_time:
            updates.append("end_time = :end_time")
            params["end_time"] = end_time

        if is_active:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if not updates:
            return None

        query = f"UPDATE working_hours SET {', '.join(updates)} WHERE id = :id"
                
        await conn.execute(text(query), params)
        await conn.commit()

        retrieve_query = await conn.execute(text("SELECT * FROM working_hours WHERE id = :id"), {"id": id})
        recent_wk = retrieve_query.mappings().one_or_none()

    return recent_wk

async def assign_procedure(organization_id: int, professional_id: int, procedure_id: int, is_active: bool) -> bool:
    async with engine.connect() as conn:
        create_query = """
        INSERT INTO professional_procedures (organization_id, professional_id, procedure_id, is_active)
        VALUES (:organization_id, :professional_id, :procedure_id, :is_active)
        """
        await conn.execute(text(create_query), {"organization_id": organization_id, "professional_id": professional_id,
                                                "procedure_id": procedure_id, "is_active": is_active})
        await conn.commit()

    return True

async def change_procedure_is_active(organization_id: int, professional_id: int, procedure_id: int, is_active: bool) -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE professional_procedures SET is_active = :is_active"), 
                           {"is_active": is_active, "organization_id": organization_id, "professional_id": professional_id, "procedure_id": procedure_id})
        await conn.commit()

    return True

async def change_buffer_time(id: int, buffer_time_minutes: int) -> dict | None:
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE professionals SET buffer_time_minutes = : buffer_time_minutes WHERE id = :id"),
                           {"buffer_time_minutes": buffer_time_minutes, "id": id})
        await conn.commit()

        query = await conn.execute(text("SELECT * FROM professionals WHERE id = :id"), {"id": id})
        updated_info = query.mappings().one_or_none()

    return updated_info
