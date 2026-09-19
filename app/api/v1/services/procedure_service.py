"""
All services related to procedure management used across Booking Engine routes.
Includes services for professional-procedure relations
"""

from decimal import Decimal

from sqlalchemy import text

from app.api.v1.services.permission_service import is_owner, is_root
from app.database import engine


# DATABASE OPERATIONS
# PROCEDURES SERVICES
async def create_procedure(organization_id: int, name: str, description: str | None, duration_minutes: int, price: Decimal, is_active: bool) -> int | None:
    """
    Creates a new procedure for an organization.

    Args:
        organization_id: The ID of the organization creating the procedure
        name: The procedure name
        description: The procedure description (optional)
        duration_minutes: The procedure duration in minutes
        price: The procedure price
        is_active: Whether the procedure is active immediately

    Returns:
        int | None: The created procedure ID, or None if no record was created
    """
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
    """
    Retrieves a procedure by its unique ID.

    Args:
        id: The procedure ID to fetch

    Returns:
        dict | None: The procedure record as a dictionary, or None if it does not exist
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM procedures WHERE id = :id"), {"id": id})
        procedure = query.mappings().one_or_none()

    return procedure

async def list_procedures_by_org(organization_id: int, is_active: bool = True) -> list[dict] | None:
    """
    Lists procedures belonging to an organization.

    Args:
        organization_id: The organization ID to query
        is_active: Whether to filter only active procedures

    Returns:
        list[dict] | None: The matching procedure records, or None if no records are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM procedures WHERE organization_id = :organization_id AND is_active = :is_active"),
                                   {"organization_id": organization_id, "is_active": is_active})
        results = query.mappings().all()

        registered_procedures = [dict(proc_row) for proc_row in results]

    return registered_procedures

async def update_procedure(id: int, name: str | None, description: str | None, duration_minutes: str | None, price: Decimal | None, is_active: bool | None) -> dict | None:
    """
    Updates selected fields on an existing procedure.

    Args:
        id: The procedure ID to update
        name: The new procedure name (optional)
        description: The new description (optional)
        duration_minutes: The new duration in minutes (optional)
        price: The new pricing value (optional)
        is_active: The active status to assign (optional)

    Returns:
        dict | None: The updated procedure record, or None if no fields were changed
    """
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
    """
    Toggles the active status of a procedure.

    Args:
        id: The procedure ID to update
        is_active: The new active status value

    Returns:
        bool: True when the update succeeds
    """
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE procedures SET is_active = :is_active WHERE id = :id"), {"is_active": is_active, "id": id})

    return True

# PROFESSIONAL-PROCEDURES RELATIONS SERVICES
async def create_professional_procedure(organization_id: int, professional_id: int, procedure_id: int, is_active: int) -> bool | None:
    """
    Creates the relationship between a professional and a procedure.

    Args:
        organization_id: The organization owning the relationship
        professional_id: The professional ID
        procedure_id: The procedure ID
        is_active: The activation state for the relationship

    Returns:
        bool | None: True when the relationship is created, otherwise None
    """
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

async def search_professional_procedure_unique(organization_id: int, professional_id: int, procedure_id: int, is_active: bool | None) -> dict | None:
    """
    Fetches a specific professional-procedure linkage by its unique identifiers.

    Args:
        organization_id: The organization ID
        professional_id: The professional ID
        procedure_id: The procedure ID
        is_active: Optional active-status filter

    Returns:
        dict | None: The matching relationship record, or None if no match is found
    """
    async with engine.connect() as conn:
        search_query = """
        SELECT * FROM professional_procedures
        WHERE organization_id = :organization_id
        AND professional_id = :professional_id
        AND procedure_id = :procedure_id AND is_active = :is_active
        """
        query = await conn.execute(text(search_query), {"organization_id": organization_id, "professional_id": professional_id,
                                                        "procedure_id": procedure_id, "is_active": is_active})
        results = query.mappings().one_or_none()

    return results

async def list_professional_procedures(organization_id: int, professional_id: int | None, procedure_id: int | None, is_active: bool = True) -> list[dict] | None:
    """
    Lists professional-procedure relationships for the given filters.

    Args:
        organization_id: The organization ID to filter by
        professional_id: The professional ID filter (optional)
        procedure_id: The procedure ID filter (optional)
        is_active: Whether to include only active relationships

    Returns:
        list[dict] | None: Matching relationship records, or None if no records are found
    """
    async with engine.connect() as conn:
        search_query = """
            SELECT *
                FROM professional_procedures
                WHERE organization_id = :organization_id
                AND professional_id = :professional_id
                AND procedure_id = :procedure_id
                AND is_active = :is_active
        """
        professional_procedures = await conn.execute(text(search_query), {"organization_id": organization_id, "professional_id": professional_id,
                                                                          "procedure_id": procedure_id, "is_active": is_active})
        results = professional_procedures.mappings().all()

        registered_pp = [dict(pp_dict) for pp_dict in results]

        return registered_pp

async def change_pp_is_active(organization_id: int, professional_id: int, procedure_id: int, is_active: bool) -> bool:
    """
    Updates the active status of a professional-procedure relationship.

    Args:
        organization_id: The organization ID for the relationship
        professional_id: The professional ID
        procedure_id: The procedure ID
        is_active: The new active status value

    Returns:
        bool: True when the update succeeds
    """
    async with engine.begin() as conn:
        update_query = """
        UPDATE professional_procedures SET is_active = :is_active
        WHERE organization_id = :organization_id AND professional_id = :professional_id AND procedure_id = :procedure_id
        """
        await conn.execute(text(update_query), {"is_active": is_active, "organization_id": organization_id, "professional_id": professional_id, "procedure_id": procedure_id})

    return True

# Access verification function
async def check_procedure_access(user_id: int, organization_id: int) -> bool:
    """
    Validates whether a user can access procedure features for an organization.
    OWNER and ROOT can access it.

    Args:
        user_id: The user ID to validate
        organization_id: The organization context to validate against

    Returns:
        bool: True if the user has access, otherwise False
    """
    root = await is_root(user_id)
    owner = await is_owner(user_id, organization_id)

    return bool(root or owner)