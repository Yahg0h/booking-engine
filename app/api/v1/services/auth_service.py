"""
All services related to authentication used across all Booking Engine routes.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request

from app.api.v1.services.password_service import hash_password, verify_password
from app.api.v1.services.user_service import search_user_by_email
from app.config import settings

# ==========================================
# JWT TOKEN MANAGEMENT
# ==========================================

def create_jwt_token(user_id: int) -> str:
    """
    Create a JWT token with expiration.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.TOKEN_EXPIRATION_MINS)
    payload = {
        "sub": str(user_id),
        "exp": expire
    }
    token = jwt.encode(payload, settings.JWT_SECRET, settings.ALGORITHM)
    return token


def decode_token(token: str, ignore_exp: bool = False) -> int:
    """
    Decode a JWT token and return user_id.
    """
    try:
        # If ignore_exp=True, then ignore the expiration date
        options = {"verify_exp": not ignore_exp}
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM], options=options)
        user_id = payload.get("sub")
        # If there isn't a valid user_id in the token, return error
        if not user_id:
            raise ValueError("Invalid Token: no user_id")
        # Else, return the user_id
        return int(user_id)
    except Exception as e:
        raise ValueError(f"Token decoding failed: {str(e)}")

async def verify_user_token(request: Request) -> int:
    """
    Extract JWT from Authorization header (Bearer token).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized: Missing token.")
    
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid token format.")
    
    try:
        user_id = decode_token(token, ignore_exp=False)
        return user_id
    except ValueError:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid token.")

async def get_current_user_optional(request: Request) -> int | None:
    """
    Optional: extract JWT from Authorization header.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            return None
        user_id = decode_token(token, ignore_exp=False)
        return user_id
    except (ValueError, IndexError):
        return None

async def authenticate_user(email: str, password: str) -> int | None:
    # Search user by its email
    user = await search_user_by_email(email)

    # If not found, raise ValueError
    if not user:
        raise ValueError("Email not found or doesn't exist.")

    # If passwords don't match, return None
    if not verify_password(password, user["password_hash"]):
        return None

    # If credentials are correct, return user id
    return user["id"]