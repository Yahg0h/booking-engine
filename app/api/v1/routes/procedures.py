from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.schemas.schemas import ProcedureCreate, ProcedureUpdate
from app.api.v1.services.auth_service import (
    get_current_user_optional,
    verify_user_token,
)
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.procedure_service import (
    change_procedure_is_active,
    create_procedure,
    list_procedures_by_org,
    search_procedure_by_id,
    update_procedure,
)
from app.api.v1.services.user_service import search_user_by_id

# Configure router
router = APIRouter(prefix="/v1")

# CREATE a procedure
@router.post("/procedures", status_code=201)
async def create_procedure_route(procedure: ProcedureCreate, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the OWNER of the selected organization
    is_owner = await search_user_by_id(user_id)

    # If it isn't, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == procedure.organization_id) or is_owner["organization_id"] != procedure.organization_id:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, create procedure that is going to be offered by the company
    recent_procedure_id = await create_procedure(procedure.organization_id, procedure.name, procedure.description,
                                                 procedure.duration_minutes, procedure.price, procedure.is_active)

    # Return success message
    if recent_procedure_id:
        success_dict = {
            "message": f"Procedure successfully created. ProcedureID = {recent_procedure_id}, OrgID = {procedure.organization_id}"
        }

        return success_dict

# READ all procedures offered by a organization (public route)
@router.get("/procedures/organization/{id}", status_code=200)
async def get_procedures_by_organization(id: int, user_id: int = Depends(get_current_user_optional)):
    # Check if the organization exists
    is_org_exist = await search_organization_by_id(id)

    # If it doesn't, return 404
    if not is_org_exist:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # Get all registered procedures under a organization
    registered_procedures = await list_procedures_by_org(id)

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
async def update_procedure_route(id: int, procedure: ProcedureUpdate, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the OWNER of the selected organization
    is_owner = await search_user_by_id(user_id)
    procedure_info = await search_procedure_by_id(id)

    # If procedure doesn't exist, return 404
    if not procedure_info:
        raise HTTPException(status_code=404, detail="Procedure not found or it isn't offered.")

    # Else, check the owner validation, If it isn't, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == procedure_info["organization_id"]) or is_owner["organization_id"] != procedure_info["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # If all well, update the procedure
    updated_procedure = await update_procedure(id, procedure.name, procedure.description, procedure.duration_minutes, 
                                               procedure.price, procedure.is_active)

    # Return the updated procedure
    return updated_procedure

# DELETE a procedures information
@router.delete("/procedures/{id}", status_code=200)
async def delete_procedure(id: int, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the OWNER of the selected organization
    is_owner = await search_user_by_id(user_id)
    procedure_info = await search_procedure_by_id(id)

    # If procedure doesn't exist, return 404
    if not procedure_info:
        raise HTTPException(status_code=404, detail="Procedure not found or it isn't offered.")

    # Else, check the owner validation, If it isn't, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == procedure_info["organization_id"]) or is_owner["organization_id"] != procedure_info["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.") 

    # Change procedure is_active to false
    is_deleted = await change_procedure_is_active(id, False)

    if is_deleted:
        success_dict = {
            "message": "Procedure has been successfully deactivated."
        }
        return success_dict