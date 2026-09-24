"""
All services related to user management used across all Booking Engine routes.
"""

from sqlalchemy import text

from app.api.v1.services.password_service import hash_password, verify_password
from app.api.v1.services.permission_service import is_owner, is_root
from app.database import engine


# DATABASE OPERATIONS
async def create_user(
    organization_id: int,
    name: str,
    email: str,
    password: str,
    role: str,
    is_active: bool | None = None
) -> int:
    """
    Creates a new user account and hashes the supplied password.

    Args:
        organization_id: The organization linked to the user
        name: The user's full name
        email: The user's email address
        password: The plain-text password to hash and store
        role: The user's role within the system
        is_active: Whether the user should be active immediately

    Returns:
        int: The ID of the newly created user
    """

    # Hash the user's password
    hashed_pass = hash_password(password)

    create_query = """
    INSERT INTO users (organization_id, name, email, password_hash, role, is_active)
    VALUES (:organization_id, :name, :email, :password_hash, :role, :is_active)
    """
    async with engine.begin() as conn:
        await conn.execute(text(create_query), {"organization_id": organization_id, "name": name, "email": email, "password_hash": hashed_pass,
                                                        "role": role, "is_active": is_active})

        select_query = """
        SELECT id FROM users WHERE email = :email
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(select_query), {"email": email})
        recent_user_id = query.scalar() # row to int

        return recent_user_id

async def search_user_by_email(email: str) -> dict | None:
    """
    Retrieves a user by their email address.

    Args:
        email: The user's email address

    Returns:
        dict | None: The user record as a dictionary, or None if it does not exist
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email})
        results = query.mappings().one_or_none() # row to dict

        return results

async def search_user_by_id(id: int) -> dict | None:
    """
    Retrieves a user by their unique ID.

    Args:
        id: The user ID to fetch

    Returns:
        dict | None: The user record as a dictionary, or None if it does not exist
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": id})
        results = query.mappings().one_or_none()

        return results

async def list_all_users(is_active: bool = True) -> list[dict] | None:
    """
    Lists users based on the active status filter.

    Args:
        is_active: Filters the results to active users when True

    Returns:
        list[dict] | None: Matching user records, or None if no records are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE is_active = :is_active"), {"is_active": is_active})
        results = query.mappings().all()

        if not results:
            return None

        registered_users = [dict(user_row) for user_row in results]

        return registered_users

async def list_users_by_organization(organization_id: int, is_active: bool = True) -> list[dict] | None:
    """
    Lists users belonging to an organization.

    Args:
        organization_id: The target organization ID
        is_active: Filters the results to active users when True

    Returns:
        list[dict] | None: Matching user records, or None if no records are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE organization_id = :organization_id AND is_active = :is_active"),
                                   {"organization_id": organization_id, "is_active": is_active})
        results = query.mappings().all()

        if not results:
            return None

        registered_org_users = [dict(user_row) for user_row in results]

        return registered_org_users

async def list_users_by_role(role: str, is_active: bool = True) -> list[dict] | None:
    """
    Lists users filtered by a specific role.

    Args:
        role: The user role to filter by
        is_active: Filters the results to active users when True

    Returns:
        list[dict] | None: Matching user records, or None if no records are found
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE role = :role AND is_active = :is_active"),
                                   {"role": role, "is_active": is_active})
        results = query.mappings().all()

        if not results:
            return None

        registered_role_users = [dict(user_row) for user_row in results]

        return registered_role_users

async def list_users_filtered(organization_id: int | None, role: int | None, is_active: bool | None, user_role: str) -> list[dict] | None:
    """
    Lists users with organization and role filters based on the acting user's permissions.

    Args:
        organization_id: The organization ID filter for owner-level access
        role: The role filter value
        is_active: The active-status filter value
        user_role: The role of the acting user determining access scope

    Returns:
        list[dict] | None: Matching user records, or None if no records are found

    Raises:
        ValueError: If a staff member tries to query a section they are not allowed to access
    """
    async with engine.connect() as conn:
        query = "SELECT * FROM users WHERE 1=1"
        params = {}

        if role is not None:
            query += " AND role = :role"
            params["role"] = role
        if is_active is not None:
            query += " AND is_active = :is_active"
            params["is_active"] = is_active

        if user_role == "ROOT":
            pass
        elif user_role == "OWNER":
            query += " AND organization_id = :organization_id"
            params["organization_id"] = organization_id
        else:
            raise ValueError("Staff members aren't allowed to view this section.")

        result = await conn.execute(text(query), params)
        users = result.mappings().all()

        filtered_users = [dict(user_row) for user_row in users]

    return filtered_users


async def update_user_admin(user_id: int, name: str, email: str, password: str, role: str, is_active: bool) -> dict | None:
    """
    Updates a user's profile fields from an administrative context.

    Args:
        user_id: The user ID to update
        name: The new user name
        email: The new user email
        password: The new plain-text password to hash and store
        role: The new user role
        is_active: The new active status

    Returns:
        dict | None: The updated user record, or None if no fields were changed
    """
    async with engine.begin() as conn:
        # Build dynamic query where only the fields chosen to be changed get updated
        updates = []
        params = {"user_id": user_id}

        if name:
            updates.append("name = :name")
            params["name"] = name

        if email:
            updates.append("email = :email")
            params["email"] = email

        if password:
            password = hash_password(password)

            updates.append("password_hash = :password_hash")
            params["password_hash"] = password

        if role:
            updates.append("role = :role")
            params["role"] = role

        if is_active is not None:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if not updates:
            return None

        query = f"UPDATE users SET {', '.join(updates)} WHERE id = :user_id"

        await conn.execute(text(query), params)

        updated_user = await search_user_by_id(user_id)

        return updated_user

async def update_own_profile(user_id: int, name: str | None, email: str | None, password: str | None, current_password: str) -> dict | None:
    """
    Updates the authenticated user's own profile after password validation.

    Args:
        user_id: The current user's ID
        name: The new display name (optional)
        email: The new email address (optional)
        password: The new plain-text password (optional)
        current_password: The current password used for verification

    Returns:
        dict | None: The updated user record, or None if no fields were changed

    Raises:
        ValueError: If the current password is incorrect
    """
    # Search user info and verify password before opening transaction
    user = await search_user_by_id(user_id)

    # Verify if the current_password is correct
    is_match = verify_password(current_password, user["password_hash"])

    if not is_match:
        raise ValueError("Current password is incorrect. Please Try Again.")

    # Build dynamic query where only the fields chosen to be changed get updated
    updates = []
    params = {"user_id": user_id}

    if name is not None:
        updates.append("name = :name")
        params["name"] = name

    if email is not None:
        updates.append("email = :email")
        params["email"] = email

    if password is not None:
        password = hash_password(password)

        updates.append("password_hash = :password_hash")
        params["password_hash"] = password

    if not updates:
        return None

    async with engine.begin() as conn:
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = :user_id"

        await conn.execute(text(query), params)

    updated_user = await search_user_by_id(user_id)

    return updated_user

async def change_user_is_active(user_id: int, is_active: bool) -> bool:
    """
    Toggles the active status of a user account.

    Args:
        user_id: The user ID to update
        is_active: The new active status value

    Returns:
        bool: True when the update succeeds
    """
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE users SET is_active = :is_active WHERE id = :user_id"), {"is_active": is_active, "user_id": user_id})

    return True

async def check_user_role(user_id: int, role: str) -> bool:
    """
    Checks whether a user has a specific role.

    Args:
        user_id: The user ID to evaluate
        role: The expected role value

    Returns:
        bool: True if the user's role matches the expected value, otherwise False
    """
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT role FROM users WHERE id = :user_id"), {"user_id": user_id})
        results = query.mappings().one_or_none()

        if not results:
            return False
        return results["role"] == role

# Access verification function
async def check_user_access(user_id: int, organization_id: int) -> bool:
    """
    Validates whether a user can access user-management resources for an organization.
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
