from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.schemas.schemas import UserCreate, UserUpdateAdmin
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
async def create_account(user: UserCreate, user_id: int | None = Depends(verify_user_token)):
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

    # Return success message
    success_dict = {
        "message": f"ROOT: User account created successfully. UserID = {new_account_id}, OrgID = {user.organization_id}."
    }
    return success_dict

# READ all users information
@router.get("/users", status_code=200)
async def get_users(user_id: int | None = Depends(verify_user_token)):
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
async def elevated_user_update(id: int, user: UserUpdateAdmin, user_id: int | None = Depends(verify_user_token)):
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

    # Else, return the newly updated user info
    return is_updated

@router.delete("/users/{id}", status_code=200)
async def delete_user(id: int, user_id: int | None = Depends(verify_user_token)):
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
        success_dict = {
            "message": f"ROOT: User of id {id} has been deactivated."
        }

        return success_dict
        