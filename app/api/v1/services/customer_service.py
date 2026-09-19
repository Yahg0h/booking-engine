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
    """
    Creates a customer record for an organization.

    Args:
        organization_id: The organization that owns the customer
        name: The customer's full name
        email: The customer's email address (optional)
        phone: The customer's phone number (optional)
        is_active: Whether the customer should be active immediately

    Returns:
        int | None: The created customer ID, or None if no record was created
    """
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
    """
    Retrieves a customer by their unique ID.

    Args:
        customer_id: The customer ID to fetch

    Returns:
        dict | None: The customer record as a dictionary, or None if it does not exist
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM customers WHERE id = :id"), {"id": customer_id})
        results = query.mappings().one_or_none()

    return results

async def list_customers_filtered(organization_id: int,
                                  email: str | None,
                                  phone: str | None,
                                  last_appointment_at: datetime | None,
                                  is_active: bool = True
) -> list[dict] | None:
    """
    Lists customers using a set of optional filters.

    Args:
        organization_id: The organization ID filter
        email: Email filter (optional)
        phone: Phone filter (optional)
        last_appointment_at: Last appointment date filter (optional)
        is_active: Active status filter

    Returns:
        list[dict] | None: Matching customer records, or None if no results are found
    """
    async with engine.connect() as conn:
        query = "SELECT * FROM customers WHERE 1=1"
        params = {}

        if organization_id is not None:
            query += " AND organization_id = :organization_id"
            params["organization_id"] = organization_id
        if email is not None:
            query += " AND email = :email"
            params["email"] = email
        if phone is not None:
            query += " AND phone = :phone"
            params["phone"] = phone
        if last_appointment_at is not None:
            query += " AND last_appointment_at = :last_appointment_at"
            params["last_appointment_at"] = last_appointment_at
        if is_active is not None:
            query += " AND is_active = :is_active"
            params["is_active"] = is_active

        results = await conn.execute(text(query), params)
        customers = results.mappings().all()

        registered_customers = [dict(customer_row) for customer_row in customers]

    return registered_customers

async def update_customers(id: int, name: str | None, email: str | None, phone: str | None, is_active: bool | None) -> dict | None:
    """
    Updates the editable fields of a customer record.

    Args:
        id: The ID of the customer to update
        name: The new customer name (optional)
        email: The new customer email (optional)
        phone: The new customer phone (optional)
        is_active: The new active status (optional)

    Returns:
        dict | None: The updated customer record, or None if no fields were changed
    """
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
    """
    Toggles the active status of a customer.

    Args:
        id: The customer ID to update
        is_active: The desired active status

    Returns:
        bool | None: True when the update succeeds, otherwise None
    """
    async with engine.begin() as conn:
        update_query = """
        UPDATE customers SET is_active = :is_active WHERE id = :id
        """
        await conn.execute(text(update_query), {"is_active": is_active, "id": id})

    return True

async def update_customer_last_appointment(customer_id: int, last_appointment_at: datetime) -> bool:
    """
    Updates the timestamp of the customer's most recent appointment.

    Args:
        customer_id: The customer whose last appointment timestamp will be updated
        last_appointment_at: The timestamp to store

    Returns:
        bool: True when the timestamp update is successful
    """
    async with engine.begin() as conn:
        update_query = """
        UPDATE customers SET last_appointment_at = :last_appointment_at WHERE id = :id
        """
        await conn.execute(text(update_query), {"last_appointment_at": last_appointment_at, "id": customer_id})

    return True

# Access verification function
async def check_customer_access(user_id: int, organization_id: int, allow_staff: bool = True):
    """
    Validates whether a user can access customer records for a specific organization.

    Args:
        user_id: The ID of the user being validated
        organization_id: The organization the user is trying to access
        allow_staff: If True, staff members may access the records when they belong to the same organization, othwerwise OWNER and ROOT only

    Returns:
        bool: True when the user has access, otherwise False
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
