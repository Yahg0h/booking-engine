import logging

from app.logging_config import sanitize_for_logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import UserCreate, UserUpdateAdmin, UserUpdateOwn
from app.api.v1.services.audit_service import (
    get_ip_from_request,
    log_action,
    sanitize_audit_values,
)
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.permission_service import is_root
from app.api.v1.services.user_service import (
    change_user_is_active,
    check_user_access,
    create_user,
    list_users_filtered,
    search_user_by_email,
    search_user_by_id,
    update_own_profile,
    update_user_admin,
)

# Configure router
router = APIRouter(prefix="/v1")

# CREATE a user staff account
@router.post("/users", status_code=201)
async def create_staff(request: Request, user: UserCreate, user_id: int | None = Depends(verify_user_token)):
    # Check access (owner or root only)
    if not await check_user_access(user_id, user.organization_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Check if the to-be added staff email is already registered; if it is, return 409
    if await search_user_by_email(user.email):
        raise HTTPException(status_code=409, detail="Staff email is already registered.")

    # If the current user has access, make sure the account to be created is a staff account
    user.role = "STAFF"

    # Add staff user account
    new_staff_id = await create_user(
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
        entity_id=new_staff_id,
        old_values=None,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====

    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"User staff account created: id={new_staff_id}, "
        f"org_id={user.organization_id}"
    )

    # Return success message
    success_dict = {
        "message": f"Staff user account created successfully. UserID = {new_staff_id}, OrgID = {user.organization_id}."
    }
    return success_dict

# CREATE a user owner account (root-account only)
@router.post("/users/owners", status_code=201)
async def create_owner(request: Request, user: UserCreate, user_id: int | None = Depends(verify_user_token)):
    # Check if the current user is a ROOT account
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")
 
    # Check if the to-be added owner email is already registered; if it is, return 409
    if await search_user_by_email(user.email):
        raise HTTPException(status_code=409, detail="Owner email is already registered.")
 
    # If the current user is a ROOT account, make sure the account to be created is an owner account
    user.role = "OWNER"
 
    # Add owner user account
    new_owner_id = await create_user(
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
        entity_id=new_owner_id,
        old_values=None,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====
    
    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"User owner account created: id={new_owner_id}, "
        f"org_id={user.organization_id}"
    )

    # Return success message
    success_dict = {
        "message": f"Owner user account created successfully. UserID = {new_owner_id}, OrgID = {user.organization_id}."
    }
    return success_dict

# READ users information (all users for ROOT, all users in organization for OWNER)
@router.get("/users", status_code=200)
async def get_users(role: str | None = None, is_active: bool | None = None, user_id: int | None = Depends(verify_user_token)):
    # Get the current user's role and organization
    current_user = await search_user_by_id(user_id)

    # Get all users based on the filters
    try:
        users_list = await list_users_filtered(current_user["organization_id"], role, is_active, current_user["role"])
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Return users list
    return users_list

# Read a specific user information
@router.get("/users/{id}", status_code=200)
async def get_user(id: int, user_id: int | None = Depends(verify_user_token)):
    # Get the selected users information
    user_info = await search_user_by_id(id)

    # If it doesn't exist, return 404
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found or doesn't exist.")

    # Check if the current user is root or the owner of the user's organization
    if await check_user_access(user_id, user_info["organization_id"]):
        return user_info
    else:
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

# UPDATE a user's information (User-only)
@router.patch("/users/{id}", status_code=200)
async def update_user_info(request: Request, id: int, user: UserUpdateOwn, user_id: int | None = Depends(verify_user_token)):
    # Check if the current user's is the user of id 'id'; if it isn't, return 403
    if id != user_id:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, update user info and return success message
    try:
        is_updated = await update_own_profile(id, user.name, user.email, user.password, user.current_password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

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
        f"User-updated user account: id={id}, "
        f"org_id={user_organization_id}, "
        f"email={sanitize_for_logging(new_values.get('email'), 'email') if 'email' in new_values else 'N/A'},"
        f"field_changed={list(new_values.keys())}"
    )

    # Else, return the newly updated user info
    return is_updated

# UPDATE a user's information (Admin - root and owner Only)
@router.patch("/users/admin/update/{id}", status_code=200)
async def elevated_user_update(request: Request, id: int, user: UserUpdateAdmin, user_id: int | None = Depends(verify_user_token)):
    # Get the selected user's organization id
    user_info = await search_user_by_id(id)

    # If it doesn't exist, return 404
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found or doesn't exist.")

    # Check if the current user isn't a OWNER of the current users organization or a ROOT account, return 403
    if not await check_user_access(user_id, user_info["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, update user info and return success message
    is_updated = await update_user_admin(id, user.name, user.email, user.password, user.role, user.is_active)

    # If the server didn't receive a user updated info dict, return 400
    if not is_updated:
        raise HTTPException(status_code=400, detail="An error occured while updating the user's information")

    # ==== AUDIT LOGS ENTRY ====
    # Add new values to a dict and log action
    old_values = user_info
    new_values = {}
    if user.name is not None: new_values["name"] = user.name
    if user.email is not None: new_values["email"] = user.email
    if user.role is not None: new_values["role"] = user.role
    if user.is_active is not None: new_values["is_active"] = user.is_active

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
        action='UPDATE',
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
        f"Admin-updated user account: id={id}, "
        f"org_id={user_organization_id}, "
        f"email={sanitize_for_logging(new_values.get('email'), 'email') if 'email' in new_values else 'N/A'},"
        f"field_changed={list(new_values.keys())}"
    )

    # Else, return the newly updated user info
    return is_updated

@router.delete("/users/{id}", status_code=200)
async def delete_user(request: Request, id: int, user_id: int | None = Depends(verify_user_token)):
    # Get the selected user's organization id
    user_info = await search_user_by_id(id)

    # If it doesn't exist, return 404
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found or doesn't exist.")

    # Check if the current user isn't a OWNER of the current users organization or a ROOT account, return 403
    if not await check_user_access(user_id, user_info["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

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
            f"User account deleted: id={id}, "
            f"org_id={user_organization_id}"
        )

        success_dict = {
            "message": f"User of id {id} has been deactivated."
        }

        return success_dict
        