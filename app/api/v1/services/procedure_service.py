"""
All services related to procedure management used across Booking Engine routes.
Includes services for professional-procedure relations
"""

from decimal import Decimal

from sqlalchemy import text

from app.database import engine


# DATABASE OPERATIONS
# PROCEDURES SERVICES
async def create_procedure(organization_id: int, name: str, description: str | None, duration_minutes: int, price: Decimal, is_active: bool) -> int | None:
    async with engine.begin() as conn:
        create_query = """
        INSERT INTO procedures (organization_id, name, description, duration_minutes, price, is_active)
        VALUES (:organization_id, :name, :description, :duration_minutes, :price, :is_active)
        """
        await conn.execute(text(create_query), {"organization_id": organization_id, "name": name, "description": description,
                                               "duration_minutes": duration_minutes, "price": price, "is_active": is_active})

        select_query = """
        SELECT id FROM procedures
        WHERE organization_id = :organization_id AND name = :name
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(select_query), {"organization_id": organization_id, "name": name})
        recent_procedure = query.scalar()

    return recent_procedure

async def search_procedure_by_id(id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM procedures WHERE id = :id"), {"id": id})
        procedure = query.mappings().one_or_none()

    return procedure

async def list_procedures_by_org(organization_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM procedures WHERE organization_id = :organization_id"), {"organization_id": organization_id})
        results = query.mappings().all()

        registered_procedures = [dict(proc_row) for proc_row in results]

    return registered_procedures

async def update_procedure(id: int, name: str | None, description: str | None, duration_minutes: str | None, price: Decimal | None, is_active: bool | None) -> dict | None:
    async with engine.begin() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"id": id}

        if name is not None:
            updates.append("name = :name")
            params["name"] = name

        if description is not None:
            updates.append("description = :description")
            params["description"] = description

        if duration_minutes is not None:
            updates.append("duration_minutes = :duration_minutes")
            params["duration_minutes"] = duration_minutes

        if price is not None:
            updates.append("price = :price")
            params["price"] = price

        if is_active is not None:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if not updates:
            return None

        query = f"UPDATE procedures SET {', '.join(updates)} WHERE id = :id"
                
        await conn.execute(text(query), params)

        retrieve_query = await conn.execute(text("SELECT * FROM procedures WHERE id = :id"), {"id": id})
        updated_proc = retrieve_query.mappings().one_or_none()

    return updated_proc

async def change_procedure_is_active(id: int, is_active: bool) -> bool:
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE procedures SET is_active = :is_active WHERE id = :id"), {"is_active": is_active, "id": id})

    return True

# PROFESSIONAL-PROCEDURES RELATIONS SERVICES
async def create_professional_procedure(organization_id: int, professional_id: int, procedure_id: int, is_active: int) -> bool | None:
    create_query = """
    INSERT INTO professional_procedures (organization_id, professional_id, procedure_id, is_active)
    VALUES (:organization_id, :professional_id, :procedure_id, :is_active)
    """
    async with engine.begin() as conn:
        await conn.execute(text(create_query), {"organization_id": organization_id,
                                                "professional_id": professional_id,
                                                "procedure_id": procedure_id,
                                                "is_active": is_active})

    return True

async def list_procedures_by_professionals(organization_id: int, professional_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        search_query = """
        SELECT * FROM professional_procedures WHERE organization_id = :organization_id AND professional_id = :professional_id
        """
        professional_procedures = await conn.execute(text(search_query), {"organization_id": organization_id, "professional_id": professional_id})
        results = professional_procedures.mappings().all()

        registered_pp = [dict(pp_dict) for pp_dict in results]

    return registered_pp

async def list_professionals_by_procedures(organization_id: int, procedure_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        search_query = """
        SELECT * FROM professional_procedures WHERE organization_id = :organization_id AND procedure_id = :procedure_id
        """
        professional_procedures = await conn.execute(text(search_query), {"organization_id": organization_id, "procedure_id": procedure_id})
        results = professional_procedures.mappings().all()

        registered_pp = [dict(pp_dict) for pp_dict in results]

    return registered_pp

async def list_professional_procedures(organization_id: int, professional_id: int | None, procedure_id: int | None) -> list[dict] | None:
    async with engine.connect() as conn:
        search_query = """
            SELECT *
                FROM professional_procedures
                WHERE organization_id = :organization_id
                AND professional_id = :professional_id
        """
        professional_procedures = await conn.execute(text(search_query), {"organization_id": organization_id, "professional_id": professional_id, "procedure_id": procedure_id})
        results = professional_procedures.mappings().all()

        registered_pp = [dict(pp_dict) for pp_dict in results]

        return registered_pp

async def change_pp_is_active(organization_id: int, professional_id: int, procedure_id: int, is_active: bool) -> bool:
    async with engine.begin() as conn:
        update_query = """
        UPDATE professional_procedures SET is_active = :is_active
        WHERE organization_id = :organization_id AND professional_id = :professional_id AND procedure_id = :procedure_id
        """
        await conn.execute(text(update_query), {"is_active": is_active, "organization_id": organization_id, "professional_id": professional_id, "procedure_id": procedure_id})

    return True