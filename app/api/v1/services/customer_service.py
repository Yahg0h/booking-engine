"""
All services related to customer management used across Booking Engine routes.
"""
from datetime import datetime

from sqlalchemy import text

from app.api.v1.services.professional_service import search_professional_by_user_id
from app.api.v1.services.user_service import search_user_by_id
from app.database import engine


# DATABASE OPERATIONS
async def create_customer(organization_id: int, name: str, email: str | None, phone: str | None, is_active: bool) -> int | None:
    async with engine.begin() as conn:
        create_query = """
        INSERT INTO customers (organization_id, name, email, phone, is_active)
        VALUES (:organization_id, :name, :email, :phone, :is_active)
        """
        await conn.execute(text(create_query), {"organization_id": organization_id, "name": name,
                                                "email": email, "phone": phone, "is_active": is_active})

        search_query = """
        SELECT id FROM customers
        WHERE organization_id = :organization_id AND name = :name
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(search_query), {"organization_id": organization_id, "name": name})
        recent_customer = query.scalar()

    return recent_customer # id

async def search_customer_by_id(customer_id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM customers WHERE id = :id"), {"id": customer_id})
        results = query.mappings().one_or_none()

    return results

async def search_customer_by_email(email: str) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM customers WHERE email = :email"), {"email": email})
        results = query.mappings().one_or_none()

    return results

async def search_customer_by_phone(phone: str) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM customers WHERE phone = :phone"), {"phone": phone})
        results = query.mappings().one_or_none()

    return results

async def list_customers_by_organization(organization_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM customers WHERE organization_id = :organization_id"), {"organization_id": organization_id})
        results = query.mappings().all()

        registered_customers = [dict(customer_row) for customer_row in results]

    return registered_customers

async def update_customers(id: int, name: str | None, email: str | None, phone: str | None, is_active: bool | None) -> dict | None:
    async with engine.begin() as conn:
        # Build dyanmic query where only the fields chosen are updated
        updates = []
        params = {"id": id}

        if name is not None:
            updates.append("name = :name")
            params["name"] = name

        if email is not None:
            updates.append("email = :email")
            params["email"] = email

        if phone is not None:
            updates.append("phone = :phone")
            params["phone"] = phone

        if is_active is not None:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if not updates:
            return None

        query = f"UPDATE customers SET {', '.join(updates)} WHERE id = :id"
                
        await conn.execute(text(query), params)

        retrieve_query = await conn.execute(text("SELECT * FROM customers WHERE id = :id"), {"id": id})
        updated_customer = retrieve_query.mappings().one_or_none()

    return updated_customer

async def change_customer_is_active(id: int, is_active: bool) -> bool | None:
    async with engine.begin() as conn:
        update_query = """
        UPDATE customers SET is_active = :is_active WHERE id = :id
        """
        await conn.execute(text(update_query), {"is_active": is_active, "id": id})

    return True

async def update_customer_last_appointment(customer_id: int, last_appointment_at: datetime) -> bool:
    async with engine.begin() as conn:
        update_query = """
        UPDATE customers SET last_appointment_at = :last_appointment_at WHERE id = :id
        """
        await conn.execute(text(update_query), {"last_appointment_at": last_appointment_at, "id": customer_id})

    return True

# Access verification function
async def check_customer_access(user_id: int, organization_id: int, allow_staff: bool = True):
    """
    allow_staff: if True, allows OWNER + STAFF; if False, only OWNER + ROOT
    """
    is_owner = await search_user_by_id(user_id)
    is_professional = await search_professional_by_user_id(user_id)
    
    # Bools
    user_is_root = is_owner["organization_id"] is None
    user_is_owner_role = is_owner["role"] == "OWNER"
    user_owns_org = is_owner["organization_id"] == organization_id
    user_is_staff = is_professional is not None and is_professional["organization_id"] == organization_id
    
    # ROOT always passes, if not it must be OWNER + be in the same org
    if user_is_root:
        return True
    
    # If not allow_staff, rejects staff
    if not allow_staff and is_professional:
        return False
    
    # Needs to be in the same org and (be OWNER OR be STAFF, if allowed)
    if allow_staff:
        return user_owns_org and (user_is_owner_role or user_is_staff)
    else:
        return user_owns_org and user_is_owner_role
