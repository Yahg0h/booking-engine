"""
Routes for root-level organization administration.
"""
import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import OrganizationCreate, OrganizationUpdate
from app.api.v1.services.audit_service import get_ip_from_request, log_action
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.organization_service import (
    create_organization,
    search_organization_by_id,
    update_organization,
)
from app.api.v1.services.permission_service import is_root

# Configure router
router = APIRouter(prefix="/v1/root")

# CREATE a organization (root)
@router.post("/organizations", status_code=201)
async def create_org(request: Request, org_data: OrganizationCreate, user_id: int | None = Depends(verify_user_token)):
    """
    Creates a new organization for the root administrator.

    Args:
        request: The FastAPI request object
        org_data: The organization creation schema
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message confirming the organization was created

    Raises:
        HTTPException: If the current user is not a root administrator
    """
    # Check if the current account is a ROOT account; if it isn't, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Create the organization
    recent_org = await create_organization(org_data.name, org_data.slug, org_data.min_work_time, org_data.max_work_time)

    # Return the success message
    if recent_org:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "name": org_data.name,
            "slug": org_data.slug,
            "min_work_time": org_data.min_work_time,
            "max_work_time": org_data.max_work_time
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Log action
        await log_action(
            organization_id=None,
            actor_user_id=user_id,
            action='CREATE',
            entity_type='ORGANIZATION',
            entity_id=recent_org,
            old_values=None,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"ROOT: Organization created: id={recent_org}"
        )

        success_dict = {
            "message": f"ROOT: Organization successfully created. OrgID = {recent_org}."
        }

    return success_dict

# READ a organizations info (root)
@router.get("/organizations/{id}", status_code=200)
async def get_organization(id: int, user_id: int | None = Depends(verify_user_token)):
    """
    Retrieves information about a specific organization.

    Args:
        id: The ID of the organization
        user_id: The ID of the authenticated user

    Returns:
        dict: The organization information

    Raises:
        HTTPException: If the organization is not found or if the current user is not authorized to access it
    """
    # Check if the organization exists
    is_real = await search_organization_by_id(id)

    if not is_real:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # Check the current user's access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, get the organization info and return it
    org_dict = await search_organization_by_id(id)

    return org_dict

# UPDATE a organization's information (root)
@router.patch("/organizations/{id}", status_code=200)
async def update_org(request: Request, id: int, org_data: OrganizationUpdate, user_id: int | None = Depends(verify_user_token)):
    """
    Updates the information of an existing organization.

    Args:
        request: The FastAPI request object
        id: The ID of the organization
        org_data: The organization update schema
        user_id: The ID of the authenticated user

    Returns:
        dict: The updated organization information

    Raises:
        HTTPException: If the organization is not found or if the current user is not authorized to access it
    """
    # Check if the organization exists
    is_real = await search_organization_by_id(id)

    if not is_real:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # Check the current user's access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, update the organization information
    is_updated = await update_organization(id, org_data.name, org_data.slug, org_data.min_work_time, org_data.max_work_time)

    if is_updated:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {}
        if org_data.name is not None: new_values["name"] = org_data.name
        if org_data.slug is not None: new_values["slug"] = org_data.slug
        if org_data.min_work_time is not None: new_values["min_work_time"] = org_data.min_work_time
        if org_data.max_work_time is not None: new_values["max_work_time"] = org_data.max_work_time
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Log action
        await log_action(
            organization_id=id,
            actor_user_id=user_id,
            action='UPDATE',
            entity_type='ORGANIZATION',
            entity_id=id,
            old_values=is_real,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        # Sanitize time fields
        updated_values = {}
        for key, value in new_values.items():
            if key in ['min_work_time', 'max_work_time'] and value is not None:
                updated_values[key] = value.isoformat()
            else:
                updated_values[key] = value
        # Log
        logger.info(
            f"ROOT: Organization updated: id={id}, "
            f"field_changed={list(updated_values.keys())}, "
            f"min_work_time={updated_values.get('min_work_time', 'N/A')}, "
            f"max_work_time={updated_values.get('max_work_time', 'N/A')}"
        )

        return is_updated