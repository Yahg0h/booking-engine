"""
All services related to user management used across all Booking Engine routes.
"""

from sqlalchemy import text

from app.api.v1.services.password_service import hash_password
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
    async with engine.connect() as conn:
        await conn.execute(text(create_query), {"organization_id": organization_id, "name": name, "email": email, "password_hash": hashed_pass,
                                                        "role": role, "is_active": is_active})
        await conn.commit()

        query = await conn.execute(text("SELECT id FROM users WHERE id = LAST_INSERT_ID()"))
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

async def update_user(user_id: int, name: str, email: str, password: str, role: str, is_active: bool) -> bool:
    async with engine.connect() as conn:
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

        if is_active:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if not updates:
            return True

        query = f"UPDATE users SET {', '.join(updates)} WHERE id = :user_id"

        await conn.execute(text(query), params)
        await conn.commit()

        return True

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