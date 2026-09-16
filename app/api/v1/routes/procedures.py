import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import ProcedureCreate, ProcedureUpdate
from app.api.v1.services.audit_service import get_ip_from_request, log_action
from app.api.v1.services.auth_service import (
    get_current_user_optional,
    verify_user_token,
)
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.procedure_service import (
    change_procedure_is_active,
    check_procedure_access,
    create_procedure,
    list_procedures_by_org,
    search_procedure_by_id,
    update_procedure,
)

# Configure router
router = APIRouter(prefix="/v1")

# CREATE a procedure
@router.post("/procedures", status_code=201)
async def create_procedure_route(request: Request, procedure: ProcedureCreate, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the OWNER of the selected organization or root; If it isn't, return 403
    if not await check_procedure_access(user_id, procedure.organization_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, create procedure that is going to be offered by the company
    recent_procedure_id = await create_procedure(procedure.organization_id, procedure.name, procedure.description,
                                                 procedure.duration_minutes, procedure.price, procedure.is_active)

    # Return success message
    if recent_procedure_id:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "organization_id": procedure.organization_id,
            "name": procedure.name,
            "description": procedure.description,
            "duration_minutes": procedure.duration_minutes,
            "price": procedure.price,
            "is_active": procedure.is_active
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Log action
        await log_action(
            organization_id=procedure.organization_id,
            actor_user_id=user_id,
            action='CREATE',
            entity_type='PROCEDURE',
            entity_id=recent_procedure_id,
            old_values=None,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Procedure created: id={recent_procedure_id}, "
            f"org_id={procedure.organization_id}"
        )

        success_dict = {
            "message": f"Procedure successfully created. ProcedureID = {recent_procedure_id}, OrgID = {procedure.organization_id}"
        }

        return success_dict

# READ all procedures offered by a organization (public route)
@router.get("/procedures/organization/{id}", status_code=200)
async def get_procedures_by_organization(id: int, is_active: bool = True, user_id: int = Depends(get_current_user_optional)):
    # Check if the organization exists
    is_org_exist = await search_organization_by_id(id)

    # If it doesn't, return 404
    if not is_org_exist:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # Get all registered procedures under a organization
    registered_procedures = await list_procedures_by_org(id, is_active=is_active)

    # Return procedures
    return registered_procedures

# READ the information of a procedure (public route)
@router.get("/procedures/{id}", status_code=200)
async def get_procedure(id: int, user_id: int = Depends(get_current_user_optional)):
    # Check if the procedure exist
    procedure = await search_procedure_by_id(id)

    # If it doesn't, return 404
    if not procedure:
        raise HTTPException(status_code=404, detail="Procedure not found or it isn't offered.")

    # Else, return procedure info
    return procedure

# UPDATE a procedures information
@router.patch("/procedures/{id}", status_code=200)
async def update_procedure_route(request: Request, id: int, procedure: ProcedureUpdate, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the OWNER of the selected organization or root
    procedure_info = await search_procedure_by_id(id)

    # If procedure doesn't exist, return 404
    if not procedure_info:
        raise HTTPException(status_code=404, detail="Procedure not found or it isn't offered.")

    # Else, check the owner validation, If it isn't, return 403
    if not await check_procedure_access(user_id, procedure_info["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # If all well, update the procedure
    updated_procedure = await update_procedure(id, procedure.name, procedure.description, procedure.duration_minutes, 
                                               procedure.price, procedure.is_active)

    # ==== AUDIT LOGS ENTRY ====
    # Add new values to a dict and log action
    old_values = procedure_info
    new_values = {}
    if procedure.name is not None: new_values["name"] = procedure.name
    if procedure.description is not None: new_values["description"] = procedure.description
    if procedure.duration_minutes is not None: new_values["duration_minutes"] = procedure.duration_minutes
    if procedure.price is not None: new_values["price"] = procedure.price
    if procedure.is_active is not None: new_values["is_active"] = procedure.is_active

    # Get IP Address
    ip_address = get_ip_from_request(request)

    # Get organization id
    procedure_organization_id = int(procedure_info["organization_id"]) if procedure_info["organization_id"] else None

    # Log action
    await log_action(
        organization_id=procedure_organization_id,
        actor_user_id=user_id,
        action='UPDATE',
        entity_type='PROCEDURE',
        entity_id=id,
        old_values=old_values,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====

    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"Procedure updated: id={id}, "
        f"org_id={procedure_organization_id}, "
        f"price={str(new_values.get('price', 'N/A')) if 'price' in new_values else 'N/A'}, "
        f"field_changed={list(new_values.keys())}"
    )

    # Return the updated procedure
    return updated_procedure

# DELETE a procedures information
@router.delete("/procedures/{id}", status_code=200)
async def delete_procedure(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the OWNER of the selected organization or root
    procedure_info = await search_procedure_by_id(id)

    # If procedure doesn't exist, return 404
    if not procedure_info:
        raise HTTPException(status_code=404, detail="Procedure not found or it isn't offered.")

    # Else, check the owner validation, If it isn't, return 403
    if not await check_procedure_access(user_id, procedure_info["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.") 

    # Change procedure is_active to false
    is_deleted = await change_procedure_is_active(id, False)

    if is_deleted:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        old_values = procedure_info
        new_values = {
            "is_active": False
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get organization id
        procedure_organization_id = int(procedure_info["organization_id"]) if procedure_info["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=procedure_organization_id,
            actor_user_id=user_id,
            action='DELETE',
            entity_type='PROCEDURE',
            entity_id=id,
            old_values=old_values,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Procedure deleted: id={id}, "
            f"org_id={procedure_organization_id}"
        )

        success_dict = {
            "message": "Procedure has been successfully deactivated."
        }
        return success_dict