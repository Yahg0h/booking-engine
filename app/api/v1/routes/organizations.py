from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.schemas.schemas import OrganizationCreate, OrganizationUpdate
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.organization_service import (
    create_organization,
    search_organization_by_id,
    update_organization,
)
from app.api.v1.services.user_service import check_user_role, search_user_by_id

# Configure router
router = APIRouter(prefix="/v1")

# CREATE a organization (root-account only)
@router.post("/organizations", status_code=201)
async def create_org(org_data: OrganizationCreate, user_id: int | None = Depends(verify_user_token)):
    # Check if the current account is a ROOT account; if it isn't, return 403
    is_root = await check_user_role(user_id, "ROOT")
    if not is_root:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Create the organization
    recent_org = await create_organization(org_data.name, org_data.slug, org_data.min_work_time, org_data.max_work_time)

    # Return the success message
    if recent_org:
        success_dict = {
            "message": f"Organization successfully created. OrgID = {recent_org}."
        }

    return success_dict

# READ a organizations info (root and org owner account only)
@router.get("/organizations/{id}", status_code=200)
async def get_organization(id: int, user_id: int | None = Depends(verify_user_token)):
    # Check if the organization exists
    is_real = await search_organization_by_id(id)

    if not is_real:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # If it does, check if the current user is a root or the Owner of the organization
    is_root = await check_user_role(user_id, "ROOT")
    is_owner = await search_user_by_id(user_id)

    # If not, return 403
    if not is_root and (is_owner["role"] != "OWNER" or is_owner["organization_id"] != id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Else, get the organization info and return it
    org_dict = await search_organization_by_id(id)

    return org_dict

# UPDATE a organization's information (root and org owner account only)
@router.patch("/organizations/{id}", status_code=200)
async def update_org(id: int, org_data: OrganizationUpdate, user_id: int | None = Depends(verify_user_token)):
    # Check if the organization exists
    is_real = await search_organization_by_id(id)

    if not is_real:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # If it does, check if the current user is a root or the Owner of the organization
    is_root = await check_user_role(user_id, "ROOT")
    is_owner = await search_user_by_id(user_id)

    # If not, return 403
    if not is_root and (is_owner["role"] != "OWNER" or is_owner["organization_id"] != id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Else, update the organization information
    is_updated = await update_organization(id, org_data.name, org_data.slug, org_data.min_work_time, org_data.max_work_time)

    if is_updated:
        return is_updated