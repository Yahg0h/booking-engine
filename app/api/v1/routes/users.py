from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.schemas.schemas import UserCreate, UserUpdateAdmin, UserUpdateOwn
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.user_service import (
    change_user_is_active,
    check_user_role,
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
async def create_staff(user: UserCreate, user_id: int | None = Depends(verify_user_token)):
    # Check if the current user is a OWNER account
    is_owner = await check_user_role(user_id, "OWNER")
    if not is_owner:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Check if the to-be added staff email is already registered; if it is, return 409
    if await search_user_by_email(user.email):
        raise HTTPException(status_code=409, detail="Staff email is already registered.")

    # If it is a OWNER account, make sure the account to be created is a staff account
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

    # Return success message
    success_dict = {
        "message": f"Staff user account created successfully. UserID = {new_staff_id}, OrgID = {user.organization_id}."
    }
    return success_dict

# CREATE a user owner account (root-account only)
@router.post("/users/owners", status_code=201)
async def create_owner(user: UserCreate, user_id: int | None = Depends(verify_user_token)):
    # Check if the current user is a ROOT account
    is_root = await check_user_role(user_id, "ROOT")
    if not is_root:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")
 
    # Check if the to-be added owner email is already registered; if it is, return 409
    if await search_user_by_email(user.email):
        raise HTTPException(status_code=409, detail="Owner email is already registered.")
 
    # If it is a ROOT account, make sure the account to be created is an owner account
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

    # Check if the current user is root
    is_root = await check_user_role(user_id, "ROOT")
    if is_root:
        # If it, return user info
         return user_info

    # Else, check if the current user is the owner of the user 'id's organization
    possible_owner = await search_user_by_id(user_id)

    # Check if the current user is part of the selected user's organization and isn't the OWNER of the organization
    if possible_owner["organization_id"] == user_info["organization_id"] and possible_owner["role"] == "OWNER":
        return user_info
    else:
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

# UPDATE a user's information (User-only)
@router.patch("/users/{id}", status_code=200)
async def update_user_info(id: int, user: UserUpdateOwn, user_id: int | None = Depends(verify_user_token)):
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

    # Else, return the newly updated user info
    return is_updated

# UPDATE a user's information (Admin - root and owner Only)
@router.patch("/users/admin/update/{id}", status_code=200)
async def elevated_user_update(id: int, user: UserUpdateAdmin, user_id: int | None = Depends(verify_user_token)):
    # Get the selected user's organization id
    user_info = await search_user_by_id(id)

    # If it doesn't exist, return 404
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found or doesn't exist.")

    # Check if the current user isn't a OWNER of the current users organization or a ROOT account, return 403
    is_root = await check_user_role(user_id, "ROOT")
    is_owner = await search_user_by_id(user_id)

    if not (is_root or (is_owner["role"] == "OWNER" and is_owner["organization_id"] == user_info["organization_id"])):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, update user info and return success message
    is_updated = await update_user_admin(id, user.name, user.email, user.password, user.role, user.is_active)

    # If the server didn't receive a user updated info dict, return 400
    if not is_updated:
        raise HTTPException(status_code=400, detail="An error occured while updating the user's information")

    # Else, return the newly updated user info
    return is_updated

@router.delete("/users/{id}", status_code=200)
async def delete_user(id: int, user_id: int | None = Depends(verify_user_token)):
    # Get the selected user's organization id
    user_info = await search_user_by_id(id)

    # If it doesn't exist, return 404
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found or doesn't exist.")

    # Check if the current user isn't a OWNER of the current users organization or a ROOT account, return 403
    is_root = await check_user_role(user_id, "ROOT")
    is_owner = await search_user_by_id(user_id)

    if not (is_root or (is_owner["role"] == "OWNER" and is_owner["organization_id"] == user_info["organization_id"])):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, change the account is_active to false
    is_deactivated = await change_user_is_active(id, False)

    # Return success message
    if is_deactivated:
        success_dict = {
            "message": f"User of id {id} has been deactivated."
        }

        return success_dict
        