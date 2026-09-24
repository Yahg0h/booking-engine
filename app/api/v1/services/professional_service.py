"""
All services related to professional management used across Booking Engine routes.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import text

from app.api.v1.services.permission_service import is_owner, is_root
from app.database import engine


# DATABASE OPERATIONS
async def create_professionals(organization_id: int, user_id: int, name: str, buffer_time_minutes: str, is_active: bool | None) -> int:
    """
    Creates a new professional record linked to an organization and user.

    Args:
        organization_id: The organization that owns the professional record
        user_id: The user ID associated with the professional
        name: The professional's display name
        buffer_time_minutes: The default buffer time in minutes before and after appointments
        is_active: Whether the professional is active immediately

    Returns:
        int: The ID of the newly created professional record
    """
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
    """
    Retrieves a professional by their unique ID.

    Args:
        id: The professional ID to fetch

    Returns:
        dict | None: The professional record as a dictionary, or None if it does not exist
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals WHERE id = :id"), {"id": id})
        pro_dict = query.mappings().one_or_none()

    return pro_dict

async def search_professional_by_user_id(user_id: int) -> dict | None:
    """
    Retrieves the professional record linked to a specific user.

    Args:
        user_id: The user ID associated with the professional

    Returns:
        dict | None: The professional record, or None if no professional is linked to that user
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals WHERE user_id = :user_id"), {"user_id": user_id})
        pro_dict = query.mappings().one_or_none()

    return pro_dict

async def list_professionals_by_org(organization_id: int, is_active: bool = True) -> list[dict] | None:
    """
    Lists active or inactive professionals for a single organization.

    Args:
        organization_id: The organization ID to query
        is_active: Filters the results to active professionals when True

    Returns:
        list[dict] | None: Matching professional records, or None if no results are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals WHERE organization_id = :organization_id AND is_active = :is_active"),
                                   {"organization_id": organization_id, "is_active": is_active})
        professionals = query.mappings().all()

        registered_professionals = [dict(pro_dict) for pro_dict in professionals]

    return registered_professionals

async def list_all_professionals(is_active: bool = True) -> list[dict] | None:
    """
    Lists professionals across all organizations.

    Args:
        is_active: Filters the results to active professionals when True

    Returns:
        list[dict] | None: Matching professional records, or None if no results are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM professionals WHERE is_active = :is_active"), {"is_active": is_active})
        professionals = query.mappings().all()

        registered_professionals = [dict(pro_dict) for pro_dict in professionals]

    return registered_professionals

async def update_professional(id: int, organization_id: int | None, name: str | None, user_id: int | None, buffer_time_minutes: int | None, is_active: bool | None) -> dict | None:
    """
    Updates the editable information for a professional record.

    Args:
        id: The professional ID to update
        organization_id: The new organization ID (optional)
        name: The new professional name (optional)
        user_id: The new associated user ID (optional)
        buffer_time_minutes: The new buffer time in minutes (optional)
        is_active: The new active status (optional)

    Returns:
        dict | None: The updated professional record, or None if no fields were changed
    """
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
    """
    Toggles the active status of a professional record.

    Args:
        id: The professional ID to update
        is_active: The new active status value

    Returns:
        bool: True when the update succeeds
    """
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE professionals SET is_active = :is_active WHERE id = :id"), {"is_active": is_active, "id": id})

    return True

# WORKING HOURS related services

async def create_working_hours(professional_id: int, weekday: int, start_time: time, end_time: time, is_active: bool) -> int | None:
    """
    Creates a working-hours entry for a professional.

    Args:
        professional_id: The professional ID to associate with the schedule
        weekday: The weekday number for the schedule entry
        start_time: The start time for the working-hours interval
        end_time: The end time for the working-hours interval
        is_active: Whether the schedule entry is active

    Returns:
        int | None: The created working-hours ID, or None if no record was created
    """
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
    """
    Retrieves a working-hours record by ID.

    Args:
        id: The working-hours ID to fetch

    Returns:
        dict | None: The working-hours record as a dictionary, or None if it does not exist
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM working_hours WHERE id = :id"), {"id": id})
        working_hour = query.mappings().one_or_none()

    return working_hour

async def list_working_hours_by_professional(professional_id: int, is_active: bool = True) -> list[dict] | None:
    """
    Lists working-hours records for a specific professional.

    Args:
        professional_id: The professional ID to query
        is_active: Filters the results to active working-hours entries when True

    Returns:
        list[dict] | None: Matching working-hours records, or None if none are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM working_hours WHERE professional_id = :professional_id AND is_active = :is_active"),
                                   {"professional_id": professional_id, "is_active": is_active})
        results = query.mappings().all()

        registered_wks = [dict(wk_row) for wk_row in results]

    return registered_wks

async def list_active_working_hours_by_professional(professional_id: int, is_active: bool | None = True) -> list[dict] | None:
    """
    Lists working-hours records and normalizes time values for a professional.

    Args:
        professional_id: The professional ID to query
        is_active: Optional active-status filter

    Returns:
        list[dict] | None: Working-hours records with normalized time values, or None if not found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM working_hours WHERE professional_id = :professional_id AND is_active = :is_active"),
                                   {"professional_id": professional_id, "is_active": is_active})
        results = query.mappings().all()

        registered_wks = []
        for wk_row in results:
            row_dict = dict(wk_row)
            # Converta timedelta → time
            if isinstance(row_dict['start_time'], timedelta):
                row_dict['start_time'] = (datetime.min + row_dict['start_time']).time()
            if isinstance(row_dict['end_time'], timedelta):
                row_dict['end_time'] = (datetime.min + row_dict['end_time']).time()
            registered_wks.append(row_dict)

    return registered_wks

async def update_working_hours(id: int, weekday: int | None, start_time: time | None, end_time: time | None, is_active: bool | None) -> dict | None:
    """
    Updates selected fields in a working-hours record.

    Args:
        id: The working-hours ID to update
        weekday: The new weekday value (optional)
        start_time: The start time to set (optional)
        end_time: The end time to set (optional)
        is_active: The new active status (optional)

    Returns:
        dict | None: The updated working-hours record, or None if no fields were changed
    """
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

async def check_existing_weekday(weekday: int, professional_id: int) -> bool:
    """
    Checks whether a professional already has a schedule entry for a specific weekday.

    Args:
        weekday: The weekday number to validate
        professional_id: The professional ID to check

    Returns:
        bool: True if the weekday already exists for the professional, otherwise False
    """
    async with engine.connect() as conn:
        search_query = """
        SELECT * FROM working_hours WHERE weekday = :weekday AND professional_id = :professional_id
        """
        query = await conn.execute(text(search_query), {"weekday": weekday, "professional_id": professional_id})
        existing_weekday = query.mappings().one_or_none()

        return bool(existing_weekday)

# BUFFER TIME changes (owner-only)

async def change_buffer_time(id: int, buffer_time_minutes: int) -> dict | None:
    """
    Updates the buffer time setting for a professional.

    Args:
        id: The professional ID to update
        buffer_time_minutes: The buffer value in minutes

    Returns:
        dict | None: The updated professional record, or None if no record is found
    """
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE professionals SET buffer_time_minutes = :buffer_time_minutes WHERE id = :id"),
                           {"buffer_time_minutes": buffer_time_minutes, "id": id})

        query = await conn.execute(text("SELECT * FROM professionals WHERE id = :id"), {"id": id})
        updated_info = query.mappings().one_or_none()

    return updated_info

# BLACKOUTS related services (professionals only)

async def create_blackouts(professional_id: int, start_at: datetime, end_at: datetime, reason: str, status: str = "PENDING") -> int:
    """
    Creates a blackout window for a professional.

    Args:
        professional_id: The professional ID associated with the blackout
        start_at: The blackout start timestamp
        end_at: The blackout end timestamp
        reason: The reason for the blackout

    Returns:
        int: The ID of the newly created blackout record
    """
    async with engine.begin() as conn:
        create_query = """
        INSERT INTO blackouts (professional_id, start_at, end_at, reason, status)
        VALUES (:professional_id, :start_at, :end_at, :reason, :status)
        """
        await conn.execute(text(create_query), {"professional_id": professional_id, "start_at": start_at, "end_at": end_at, "reason": reason, "status": status})

        select_query = """
        SELECT id FROM blackouts
        WHERE professional_id = :professional_id
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(select_query), {"professional_id": professional_id})
        recent_blackout_id = query.scalar()

    return recent_blackout_id

async def search_blackout_by_id(id: int) -> dict | None:
    """
    Retrieves a blackout by its unique ID.

    Args:
        id: The blackout ID to fetch

    Returns:
        dict | None: The blackout record as a dictionary, or None if it does not exist
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM blackouts WHERE id = :id"), {"id": id})
        blackout = query.mappings().one_or_none()

    return blackout

async def list_blackouts_by_professional(professional_id: int) -> list[dict] | None:
    """
    Lists blackout entries for a specific professional.

    Args:
        professional_id: The professional ID to query

    Returns:
        list[dict] | None: Matching blackout records, or None if none are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM blackouts WHERE professional_id = :professional_id"), {"professional_id": professional_id})
        results = query.mappings().all()

        registered_blackouts = [dict(blackout_dict) for blackout_dict in results]

    return registered_blackouts

async def update_blackout(id: int, professional_id: int, start_at: datetime | None, end_at: datetime | None, reason: str | None) -> dict | None:
    """
    Updates an existing blackout record.

    Args:
        id: The blackout ID to update
        professional_id: The associated professional ID
        start_at: The new blackout start time (optional)
        end_at: The new blackout end time (optional)
        reason: The revised blackout reason (optional)

    Returns:
        dict | None: The updated blackout record, or None if no fields were changed
    """
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

async def approve_blackout(blackout_id: int) -> dict | None:
    """
    Approves a pending blackout.

    Args:
        id: The blackout ID to update

    Returns:
        dict | None: The updated blackout record, with the status 'ACCEPTED'
    """
    status = 'ACCEPTED'

    async with engine.begin() as conn:
        await conn.execute(text("UPDATE blackouts SET status = :status WHERE id = :id"),
                          {"status": status, "id": blackout_id})

        retrieve_query = await conn.execute(text("SELECT * FROM blackouts WHERE id = :id"),
                                           {"id": blackout_id})
        updated_blackout = retrieve_query.mappings().one_or_none()

    return updated_blackout

async def reject_blackout(blackout_id: int) -> dict | None:
    """
    Rejects a pending blackout.

    Args:
        id: The blackout ID to update

    Returns:
        dict | None: The updated blackout record, with the status 'REJECTED'
    """
    status = 'REJECTED'

    async with engine.begin() as conn:
        await conn.execute(text("UPDATE blackouts SET status = :status WHERE id = :id"),
                          {"status": status, "id": blackout_id})

        retrieve_query = await conn.execute(text("SELECT * FROM blackouts WHERE id = :id"),
                                           {"id": blackout_id})
        updated_blackout = retrieve_query.mappings().one_or_none()

    return updated_blackout

# Access verification function
async def check_professional_access(user_id: int, organization_id: int) -> bool:
    """
    Validates whether a user can access professional management functions for an organization.
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
