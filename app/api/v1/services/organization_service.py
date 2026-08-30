"""
All services related to user management used across all Booking Engine routes.
"""

from datetime import time

from sqlalchemy import text

from app.database import engine


# DATABASE OPERATIONS
async def create_organization(name: str, slug: str, min_work_time: time, max_work_time: time) -> int:
    async with engine.connect() as conn:
        create_query = """
        INSERT INTO organizations (name, slug, min_work_time, max_work_time)
        VALUES (:name, :slug, :min_work_time, :max_work_time)
        """
        await conn.execute(text(create_query), {"name": name, "slug": slug, "min_work_time": min_work_time, "max_work_time": max_work_time})
        await conn.commit()

        query = await conn.execute(text("SELECT id FROM organizations WHERE id = LAST_INSERT_ID()"))
        recent_org_id = query.scalar()

    return recent_org_id

async def search_organization_by_id(id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM organizations WHERE id = :id"), {"id": id})
        results = query.mappings().one_or_none()

    return results

async def search_organizations_by_name(name: str) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM organizations WHERE name LIKE :name"), {"name": name})
        results = query.mappings().all()

        if not results:
            return None

        registered_organizations = [dict(org_dict) for org_dict in results]

    return registered_organizations

async def search_organization_by_slug(slug: str) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM organizations WHERE slug LIKE :slug"), {"slug": slug})
        results = query.mappings().one_or_none()

    return results

async def list_all_organizations() -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM organizations"))
        results = query.mappings().all()

        if not results:
            return None

        registered_organizations = [dict(org_dict) for org_dict in results]

    return registered_organizations

async def update_organization(organization_id: int, name: str, slug: str, min_work_time: time, max_work_time: time) -> dict | None:
    async with engine.connect() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"organization_id": organization_id}

        if name:
            updates.append("name = :name")
            params["name"] = name

        if slug:
            updates.append("slug = :slug")
            params["slug"] = slug

        if min_work_time:
            updates.append("min_work_time = :min_work_time")
            params["min_work_time"] = min_work_time

        if max_work_time:
            updates.append("max_work_time = :max_work_time")
            params["max_work_time"] = max_work_time

        if not updates:
            return None

        query = f"UPDATE organizations SET {', '.join(updates)} WHERE id = :organization_id"

        await conn.execute(text(query), params)
        await conn.commit()

        retrieve_query = await conn.execute(text("SELECT * FROM organizations WHERE id = :organization_id"), {"organization_id": organization_id})
        updated_org = retrieve_query.mappings().one_or_none()

    return updated_org