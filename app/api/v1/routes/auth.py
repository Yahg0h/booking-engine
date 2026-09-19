"""
Routes for managing authentication and user access.
"""
import logging

logger = logging.getLogger(__name__)


from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import UserCreate, UserLogin
from app.api.v1.services.audit_service import get_ip_from_request, log_action
from app.api.v1.services.auth_service import (
    authenticate_user,
    create_jwt_token,
    get_current_user_optional,
)
from app.api.v1.services.user_service import (
    check_user_role,
    create_user,
    list_users_by_role,
    search_user_by_email,
)

# Configure router
router = APIRouter(prefix="/v1")

# Register Route
@router.post("/register", status_code=201)
async def register(request: Request, user: UserCreate, user_id: int | None = Depends(get_current_user_optional)):
    """
    Registers a new user account with the appropriate role permissions.

    Args:
        request: The FastAPI request object
        user: The user creation schema
        user_id: The ID of the authenticated user (optional)

    Returns:
        dict: A success message confirming the new user account was created

    Raises:
        HTTPException: If a root account already exists, if the user is not allowed to create the requested role, if the email is already registered, or if the current user lacks the required permissions
    """
    # Check if anyone is trying to create a 2nd ROOT account
    if user.role == 'ROOT':
        root_exists = await list_users_by_role("ROOT")
        if root_exists:
            raise HTTPException(status_code=409, detail="Registration failed. A root administrator account already exists. Only one root account is permitted per database instance.")

    # Check if the request is to create a OWNER account
    if user.role == 'OWNER':
        # Check if the current user can create a OWNER account (must be root account)
        is_root = await check_user_role(user_id, "ROOT")
        if not is_root:
            raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Check if the request is to create a STAFF account
    if user.role == 'STAFF':
        # Check if the current user can create a STAFF account (must be owner account)
        is_owner = await check_user_role(user_id, "OWNER")
        if not is_owner:
            raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Check the user email is already registered; if it is, return 409
    if await search_user_by_email(user.email):
        raise HTTPException(status_code=409, detail="Email is already registered.")

    # Add it to database
    new_user_id = await create_user(
        user.organization_id,
        user.name,
        user.email,
        user.password,
        user.role,
        user.is_active
        )

    # ==== AUDIT LOGS ENTRY ====
    # Add new values to a dict and log action
    new_values = {
        "organization_id": user.organization_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active
    }

    # Get IP Address
    ip_address = get_ip_from_request(request)

    # Log action
    await log_action(
        organization_id=user.organization_id,
        actor_user_id=user_id,
        action='CREATE',
        entity_type='USER',
        entity_id=new_user_id,
        old_values=None,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====

    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"User created: id={new_user_id}, "
        f"org_id={user.organization_id}"
    )

    # Return Success message
    success_dict = {
        "message": f"User created successfully. UserID = {new_user_id}."
    }
    return success_dict

# Login Route
@router.post("/login", status_code=200)
async def login(request: Request, user: UserLogin):
    """
    Authenticates a user and returns a JWT token.

    Args:
        request: The FastAPI request object
        user: The user login schema

    Returns:
        dict: An access token and token type for authenticated requests

    Raises:
        HTTPException: If the user does not exist or the password is invalid
    """
    # Search if the user exists
    try:
        is_registered = await authenticate_user(user.email, user.password)
    except ValueError as e:
        # If it doesn't, return 404
        raise HTTPException(status_code=404, detail=str(e))

    # If the passwords don't match, return 401
    if is_registered is None:
        raise HTTPException(status_code=401, detail="Wrong Password. Please Try Again.")

    # If all well, create a JWT for user access
    token = create_jwt_token(is_registered)

    # ==== AUDIT LOGS ENTRY ====
    # Get IP Address
    ip_address = get_ip_from_request(request)
    # Get the user's organization_id
    from app.api.v1.services.user_service import search_user_by_id
    user_dict = await search_user_by_id(is_registered)
    user_organization_id = int(user_dict["organization_id"]) if user_dict["organization_id"] else None

    # Log action
    await log_action(
        organization_id=user_organization_id,
        actor_user_id=is_registered,
        action='LOGIN',
        entity_type='USER',
        entity_id=None,
        old_values=None,
        new_values=None,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====

    # Return token to the user
    return {"access_token": token, "token_type": "bearer"}