from datetime import datetime, timedelta

from sqlalchemy import text

from app.api.v1.services.cache_service import acquire_lock, release_lock
from app.api.v1.services.procedure_service import search_procedure_by_id
from app.api.v1.services.professional_service import search_professional_by_user_id
from app.api.v1.services.user_service import search_user_by_id
from app.database import engine


# DATABASE OPERATIONS
async def create_appointment(organization_id: int, customer_id: int, professional_id: int, procedure_id: int,
                             start_at: datetime, status: str, end_at: datetime | None = None, notes: str | None = None) -> int | None:
    from app.api.v1.services.availability_service import availability_service
    async with engine.begin() as conn:
        # Acquire distributed lock to prevent race condition (two requests for a one slot)
        lock_key = f"lock:professional:{professional_id}:{int(start_at.timestamp())}"
        if not acquire_lock(lock_key, timeout=60):
            raise ValueError("Slot no longer available. Please try again.")

        try:
            # Check if the hour the user wants is available for booking
            available_slots = await availability_service(organization_id, professional_id, procedure_id, start_at.date())
            if start_at not in available_slots:
                # If not, raise ValueError
                raise ValueError("Selected time is not available.")

            # Get the procedure's official duration time
            # and update the estimated end time for the appointment.
            procedure = await search_procedure_by_id(procedure_id)
            end_at = start_at + timedelta(minutes=procedure["duration_minutes"])

            # Insert
            create_query = """
            INSERT INTO appointments (organization_id, customer_id, professional_id, procedure_id, start_at, status, end_at, notes)
            VALUES (:organization_id, :customer_id, :professional_id, :procedure_id, :start_at, :status, :end_at, :notes)
            """
            await conn.execute(text(create_query), {"organization_id": organization_id, "customer_id": customer_id,
                                                    "professional_id": professional_id, "procedure_id": procedure_id,
                                                    "start_at": start_at,"status": status, "end_at": end_at, "notes": notes})
            # Get the recent appointment's id and return it
            select_query = """
            SELECT id FROM appointments
            WHERE organization_id = :organization_id AND customer_id = :customer_id AND professional_id = :professional_id
            AND procedure_id = :procedure_id AND start_at = :start_at
            ORDER BY id DESC LIMIT 1
            """
            query = await conn.execute(text(select_query), {"organization_id": organization_id, "customer_id": customer_id, "professional_id": professional_id,
                                                            "procedure_id": procedure_id, "start_at": start_at})
            appointment_id = query.scalar()

            return appointment_id
        finally:
            release_lock(lock_key)

async def search_appointment_by_id(appointment_id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM appointments WHERE id = :id"), {"id": appointment_id})
        appointment = query.mappings().one_or_none()

    return appointment

async def list_appointments_by_organization(organization_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM appointments WHERE organization_id = :organization_id"), {"organization_id": organization_id})
        results = query.mappings().all()

        registered_appointments = [dict(appoint_row) for appoint_row in results]

    return registered_appointments

async def list_appointments_by_customer(customer_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM appointments WHERE customer_id = :customer_id"), {"customer_id": customer_id})
        results = query.mappings().all()

        registered_appointments = [dict(appoint_row) for appoint_row in results]
        
    return registered_appointments

async def list_appointments_by_professional(professional_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM appointments WHERE professional_id = :professional_id"), {"professional_id": professional_id})
        results = query.mappings().all()
        
        registered_appointments = [dict(appoint_row) for appoint_row in results]
        
    return registered_appointments

async def list_appointments_by_procedure(procedure_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM appointments WHERE procedure_id = :procedure_id"), {"procedure_id": procedure_id})
        results = query.mappings().all()
        
        registered_appointments = [dict(appoint_row) for appoint_row in results]
        
    return registered_appointments

async def list_appointments_by_time_frame(organization_id: int, professional_id: int, start_at: datetime, end_at: datetime) -> list[dict] | None:
    async with engine.connect() as conn:
        search_query = """
            SELECT id, start_at, end_at
            FROM appointments
            WHERE organization_id = :organization_id
              AND professional_id = :professional_id
              AND start_at < :end_at
              AND end_at > :start_at
        """
        query = await conn.execute(text(search_query), {"organization_id": organization_id, "professional_id": professional_id,
                                                        "start_at": start_at, "end_at": end_at})
        results = query.mappings().all()

        registered_appointments = [dict(appoint_row) for appoint_row in results]
                
    return registered_appointments

async def update_appointments(id: int, organization_id: int, customer_id: int,
                               professional_id: int, procedure_id: int, start_at: datetime | None,
                               end_at: datetime | None, status: str | None, notes: str | None) -> dict | None:
    from app.api.v1.services.availability_service import availability_service
    async with engine.begin() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"id": id}

        if start_at is not None and end_at is not None:
            # Check if the hour the user wants is available for booking
            available_slots = await availability_service(organization_id, professional_id, procedure_id, start_at.date())
            if start_at not in available_slots:
                # If not, raise ValueError
                raise ValueError("Selected time is not available.")

            # Get the procedure's official duration time
            # and update the estimated end time for the appointment.
            procedure = await search_procedure_by_id(procedure_id)
            end_at = start_at + timedelta(minutes=procedure["duration_minutes"])

            updates.append("start_at = :start_at")
            params["start_at"] = start_at

            updates.append("end_at = :end_at")
            params["end_at"] = end_at

        if status is not None:
            updates.append("status = :status")
            params["status"] = status

        if notes is not None:
            updates.append("notes = :notes")
            params["notes"] = notes

        if not updates:
            return None

        query = f"UPDATE appointments SET {', '.join(updates)} WHERE id = :id"

        await conn.execute(text(query), params)

        retrieve_query = await conn.execute(text("SELECT * FROM appointments WHERE id = :id"), {"id": id})
        updated_app = retrieve_query.mappings().one_or_none()

    return updated_app

async def appointment_completed(appointment_id: int) -> bool:
    async with engine.begin() as conn:
        status = 'COMPLETED'
        await conn.execute(text("UPDATE appointments SET status = :status WHERE id = :id"), {"status": status, "id": appointment_id})

    return True

async def appointment_canceled(appointment_id: int) -> bool:
    async with engine.begin() as conn:
        status = 'CANCELLED'
        await conn.execute(text("UPDATE appointments SET status = :status WHERE id = :id"), {"status": status, "id": appointment_id})

    return True

# Access verification function
async def check_appointment_access(user_id: int, organization_id: int):
    """
    APPOINTMENTS: OWNER + STAFF + ROOT can access it
    """
    is_owner = await search_user_by_id(user_id)
    is_professional = await search_professional_by_user_id(user_id)
    
    user_is_root = is_owner["organization_id"] is None
    user_is_owner_role = is_owner["role"] == "OWNER"
    user_owns_org = is_owner["organization_id"] == organization_id
    user_is_staff = is_professional is not None and is_professional["organization_id"] == organization_id
    
    if user_is_root:
        return True
    
    return user_owns_org and (user_is_owner_role or user_is_staff)