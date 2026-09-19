"""
Routes for root-level user administration.
"""
import logging

from app.logging_config import sanitize_for_logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import UserCreate, UserUpdateAdmin
from app.api.v1.services.audit_service import (
    get_ip_from_request,
    log_action,
    sanitize_audit_values,
)
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.permission_service import is_root
from app.api.v1.services.user_service import (
    change_user_is_active,
    create_user,
    list_all_users,
    search_user_by_email,
    search_user_by_id,
    update_user_admin,
)

# Configure router
router = APIRouter(prefix="/v1/root")

# CREATE a new account
@router.post("/users", status_code=201)
async def create_account(request: Request, user: UserCreate, user_id: int | None = Depends(verify_user_token)):
    """
    Creates a new user account for the root administrator.

    Args:
        request: The FastAPI request object
        user: The user creation schema
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message confirming the user account was created

    Raises:
        HTTPException: If the current user is not a root administrator, if the email is already registered, or if an invalid root account attempt is made
    """
    # Check root access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Check if the to-be added staff email is already registered; if it is, return 409
    if await search_user_by_email(user.email):
        raise HTTPException(status_code=409, detail="Staff email is already registered.")

    # If the new account to be created is root, return 409
    if user.role == "ROOT":
        raise HTTPException(status_code=409, detail="Only one root account can exist.")

    # Else, create a new user account
    new_account_id = await create_user(
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
        entity_id=new_account_id,
        old_values=None,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====

    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"ROOT: User account created: id={new_account_id}, "
        f"org_id={user.organization_id}"
    )

    # Return success message
    success_dict = {
        "message": f"ROOT: User account created successfully. UserID = {new_account_id}, OrgID = {user.organization_id}."
    }
    return success_dict

# READ all users information
@router.get("/users", status_code=200)
async def get_users(user_id: int | None = Depends(verify_user_token)):
    """
    Lists all user accounts across the system.

    Args:
        user_id: The ID of the authenticated user

    Returns:
        list: A list of all registered users

    Raises:
        HTTPException: If the current user is not authorized to access the resource
    """
    # Check root access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, get all users based on the filters
    users_list = await list_all_users()

    # Return users list
    return users_list

# Read a specific user information
@router.get("/users/{id}", status_code=200)
async def get_user(id: int, user_id: int | None = Depends(verify_user_token)):
    """
    Retrieves information about a specific user by ID.

    Args:
        id: The ID of the user
        user_id: The ID of the authenticated user

    Returns:
        dict: The user information

    Raises:
        HTTPException: If the user is not found or if the current user is not authorized to access it
    """
    # Get the selected users information
    user_info = await search_user_by_id(id)

    # If it doesn't exist, return 404
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found or doesn't exist.")

    # Check if the current user is root
    if await is_root(user_id):
        return user_info
    else:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

# UPDATE a user's information
@router.patch("/users/{id}", status_code=200)
async def elevated_user_update(request: Request, id: int, user: UserUpdateAdmin, user_id: int | None = Depends(verify_user_token)):
    """
    Updates a user's information from an administrator perspective.

    Args:
        request: The FastAPI request object
        id: The ID of the user being updated
        user: The admin user update schema
        user_id: The ID of the authenticated user

    Returns:
        dict: The updated user information

    Raises:
        HTTPException: If the user is not found, if the current user is not authorized to access the resource, or if the update operation fails
    """
    # Get the selected user's organization id
    user_info = await search_user_by_id(id)

    # If it doesn't exist, return 404
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found or doesn't exist.")

    # Check current user's access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, update user info and return success message
    is_updated = await update_user_admin(id, user.name, user.email, user.password, user.role, user.is_active)

    # If the server didn't receive a user updated info dict, return 400
    if not is_updated:
        raise HTTPException(status_code=400, detail="An error occured while updating the user's information")

    # ==== AUDIT LOGS ENTRY ====
    # Add new values to a dict and log action
    old_values = await search_user_by_id(user_id)
    new_values = {}
    if user.name is not None: new_values["name"] = user.name
    if user.email is not None: new_values["email"] = user.email

    # Get IP Address
    ip_address = get_ip_from_request(request)

    # Get user organization_id
    user_organization_id = int(old_values["organization_id"]) if old_values["organization_id"] else None

    # Filter sensive information out of old_values
    old_values = sanitize_audit_values(old_values)
    new_values = sanitize_audit_values(new_values)

    # Log action
    await log_action(
        organization_id=user_organization_id,
        actor_user_id=user_id,
        action='UPDATE',
        entity_type='USER',
        entity_id=user_id,
        old_values=old_values,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====

    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"ROOT: User account updated: id={id}, "
        f"org_id={user_organization_id}, "
        f"email={sanitize_for_logging(new_values.get('email'), 'email') if 'email' in new_values else 'N/A'},"
        f"field_changed={list(new_values.keys())}"
    )

    # Else, return the newly updated user info
    return is_updated

@router.delete("/users/{id}", status_code=200)
async def delete_user(request: Request, id: int, user_id: int | None = Depends(verify_user_token)):
    """
    Deactivates an existing user account.

    Args:
        request: The FastAPI request object
        id: The ID of the user to deactivate
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message confirming the user account was deactivated

    Raises:
        HTTPException: If the user is not found or if the current user is not authorized to access the resource
    """
    # Get the selected user's organization id
    user_info = await search_user_by_id(id)

    # If it doesn't exist, return 404
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found or doesn't exist.")

    # Check current user's access, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, change the account is_active to false
    is_deactivated = await change_user_is_active(id, False)

    # Return success message
    if is_deactivated:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        old_values = user_info
        new_values = {
            "is_active": False
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get user organization_id
        user_organization_id = int(user_info["organization_id"]) if user_info["organization_id"] else None
    
        # Filter sensive information out of old_values
        old_values = sanitize_audit_values(old_values)
        new_values = sanitize_audit_values(new_values)
    
        # Log action
        await log_action(
            organization_id=user_organization_id,
            actor_user_id=user_id,
            action='DELETE',
            entity_type='USER',
            entity_id=id,
            old_values=old_values,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====
        
        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"ROOT: User account deleted: id={id}, "
            f"org_id={user_organization_id}"
        )

        success_dict = {
            "message": f"ROOT: User of id {id} has been deactivated."
        }

        return success_dict
        