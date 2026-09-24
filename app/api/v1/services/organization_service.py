"""
All services related to organization management used across all Booking Engine routes.
"""

from datetime import time

from sqlalchemy import text

from app.api.v1.services.permission_service import is_owner, is_root
from app.database import engine


# DATABASE OPERATIONS
async def create_organization(name: str, slug: str, min_work_time: time, max_work_time: time) -> int:
    """
    Creates a new organization record.

    Args:
        name: The organization name
        slug: The unique slug used to identify the organization
        min_work_time: The organization's minimum working time for the day
        max_work_time: The organization's maximum working time for the day

    Returns:
        int: The ID of the newly created organization
    """
    async with engine.begin() as conn:
        create_query = """
        INSERT INTO organizations (name, slug, min_work_time, max_work_time)
        VALUES (:name, :slug, :min_work_time, :max_work_time)
        """
        await conn.execute(text(create_query), {"name": name, "slug": slug, "min_work_time": min_work_time, "max_work_time": max_work_time})

        select_query = """
        SELECT id FROM organizations WHERE slug = :slug
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(select_query), {"slug": slug})
        recent_org_id = query.scalar()

    return recent_org_id

async def search_organization_by_id(id: int) -> dict | None:
    """
    Retrieves an organization by its ID.

    Args:
        id: The organization ID to fetch

    Returns:
        dict | None: The organization record as a dictionary, or None if it does not exist
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM organizations WHERE id = :id"), {"id": id})
        results = query.mappings().one_or_none()

    return results

async def list_all_organizations() -> list[dict] | None:
    """
    Lists all registered organizations.

    Returns:
        list[dict] | None: A list of organization records, or None if no organizations are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM organizations"))
        results = query.mappings().all()

        if not results:
            return None

        registered_organizations = [dict(org_dict) for org_dict in results]

    return registered_organizations

async def update_organization(organization_id: int, name: str, slug: str, min_work_time: time, max_work_time: time) -> dict | None:
    """
    Updates the organization profile with the provided values.

    Args:
        organization_id: The ID of the organization to update
        name: The new organization name
        slug: The new organization slug
        min_work_time: The new minimum work time
        max_work_time: The new maximum work time

    Returns:
        dict | None: The updated organization record, or None if no fields were changed
    """
    async with engine.begin() as conn:
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

        retrieve_query = await conn.execute(text("SELECT * FROM organizations WHERE id = :organization_id"), {"organization_id": organization_id})
        updated_org = retrieve_query.mappings().one_or_none()

    return updated_org

# Access verification function
async def check_organization_access(user_id: int, organization_id: int) -> bool:
    """
    Validates whether a user can access an organization context.
    OWNER and ROOT can access it.

    Args:
        user_id: The user ID to validate
        organization_id: The organization being checked

    Returns:
        bool: True if the user is allowed to access the organization, otherwise False
    """
    root = await is_root(user_id)
    owner = await is_owner(user_id, organization_id)

    return bool(root or owner)
