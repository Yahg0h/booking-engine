"""
All services related to user management used across all Booking Engine routes.
"""

from sqlalchemy import text

from app.api.v1.services.password_service import hash_password, verify_password
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
    
    # Hash the user's password
    hashed_pass = hash_password(password)

    create_query = """
    INSERT INTO users (organization_id, name, email, password_hash, role, is_active)
    VALUES (:organization_id, :name, :email, :password_hash, :role, :is_active)
    """
    async with engine.begin() as conn:
        await conn.execute(text(create_query), {"organization_id": organization_id, "name": name, "email": email, "password_hash": hashed_pass,
                                                        "role": role, "is_active": is_active})
        await conn.commit()

        select_query = """
        SELECT id FROM users WHERE email = :email
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(select_query), {"email": email})
        recent_user_id = query.scalar() # row to int

        return recent_user_id

async def search_user_by_email(email: str) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email})
        results = query.mappings().one_or_none() # row to dict

        return results

async def search_user_by_id(id: int) -> dict | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": id})
        results = query.mappings().one_or_none()

        return results

async def list_all_users() -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users"))
        results = query.mappings().all()

        if not results:
            return None

        registered_users = [dict(user_row) for user_row in results]

        return registered_users

async def list_users_by_organization(organization_id: int) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE organization_id = :organization_id"), {"organization_id": organization_id})
        results = query.mappings().all()

        if not results:
            return None

        registered_org_users = [dict(user_row) for user_row in results]

        return registered_org_users

async def list_users_by_role(role: str) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE role = :role"), {"role": role})
        results = query.mappings().all()

        if not results:
            return None

        registered_role_users = [dict(user_row) for user_row in results]

        return registered_role_users

async def list_user_by_status(is_active: bool) -> list[dict] | None:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT * FROM users WHERE is_active = :is_active"), {"is_active": is_active})
        results = query.mappings().all()

        if not results:
            return None

        users_with_status = [dict(user_row) for user_row in results]

        return users_with_status

async def list_users_filtered(organization_id: int | None, role: int | None, is_active: bool | None, user_role: int) -> list[dict] | None:
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
        await conn.commit()

    updated_user = await search_user_by_id(user_id)

    return updated_user

async def change_user_is_active(user_id: int, is_active: bool) -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE users SET is_active = :is_active WHERE id = :user_id"), {"is_active": is_active, "user_id": user_id})
        await conn.commit()

    return True

async def check_user_role(user_id: int, role: str) -> bool:
    async with engine.connect() as conn:
        query = await conn.execute(text("SELECT role FROM users WHERE id = :user_id"), {"user_id": user_id})
        results = query.mappings().one_or_none()
    
        if not results:
            return False
        return results["role"] == role