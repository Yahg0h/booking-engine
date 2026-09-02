from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.schemas.schemas import (
    BlackoutCreate,
    ProfessionalCreate,
    ProfessionalProcedureCreate,
    ProfessionalUpdate,
    WorkingHoursCreate,
    WorkingHoursUpdate,
)
from app.api.v1.services.auth_service import (
    get_current_user_optional,
    verify_user_token,
)
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.procedure_service import (
    change_pp_is_active,
    create_professional_procedure,
    list_professional_procedures,
    search_procedure_by_id,
)
from app.api.v1.services.professional_service import (
    change_is_active,
    create_blackouts,
    create_professionals,
    create_working_hours,
    list_all_professionals,
    list_blackouts_by_professional,
    list_professionals_by_org,
    list_working_hours_by_professional,
    search_blackout_by_id,
    search_professional_by_id,
    update_professional,
    update_working_hours,
)
from app.api.v1.services.user_service import search_user_by_id

# Configure router
router = APIRouter(prefix="/v1")

# CREATE professional
@router.post("/professionals", status_code=201)
async def create_professional_route(professional: ProfessionalCreate, user_id: int = Depends(verify_user_token)):
    # Check if the current user is a OWNER of the selected professional organization
    is_owner = await search_user_by_id(user_id)

    # If the conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional.organization_id) or is_owner["organization_id"] != professional.organization_id:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, create the professional
    created = await create_professionals(professional.organization_id,
                                            professional.user_id,
                                            professional.name,
                                            professional.buffer_time_minutes,
                                            professional.is_active)

    # Return success message
    success_dict = {
        "message": f"Professional successfully created. OrgID = {professional.organization_id}, PfID = {created}, UserID = {professional.user_id}."
    }

    return success_dict

# READ all professionals in a organization
@router.get("/professionals", status_code=200)
async def get_professionals(organization_id: int, user_id: int = Depends(verify_user_token)):
    # Check if the current user is a OWNER of the selected  organization
    is_owner = await search_user_by_id(user_id)

    # If the conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == organization_id) or is_owner["organization_id"] != organization_id:
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Else, get all professionals registered under this organization
    professionals = await list_professionals_by_org(organization_id)

    # Return list
    return professionals

# READ all professionals registered across all registered organizations (root-only)
@router.get("/professionals/all", status_code=200)
async def get_all_professionals(user_id: int = Depends(verify_user_token)):
    # Check if the current user is a root account
    is_root = await search_user_by_id(user_id)

    # If it isn't, return 403
    if is_root["role"] != "ROOT":
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Else, get all registered professionals registered
    professionals = await list_all_professionals()

    # Return list
    return professionals

# READ information of a specific professional (public route)
@router.get("/professionals/{id}", status_code=200)
async def get_professional(id: int, user_id: int = Depends(get_current_user_optional)):
    # Check if the professional exists
    prof_info = await search_professional_by_id(id)

    # If it doesn't, return 404
    if not prof_info:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # Else, if it does exist, sanitize the information so only public details are given out
    professional = {
        "organization_id": prof_info["organization_id"],
        "user_id": prof_info["user_id"],
        "name": prof_info["name"]
    }

    # Return professional info
    return professional

# UPDATE a professional's information
@router.patch("/professionals/{id}", status_code=200)
async def update_professional_route(id: int, professional: ProfessionalUpdate, user_id: int = Depends(verify_user_token)):
    # Check if the current user is a OWNER of the organization which the professional is linked to
    is_owner = await search_user_by_id(user_id)
    professional_db = await search_professional_by_id(id)

    # Check if the professional exists
    if not professional_db:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional_db["organization_id"]) or is_owner["organization_id"] != professional_db["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, update the professional info
    updated_pro = await update_professional(id, professional.organization_id, professional.name, professional.user_id,
                                            professional.buffer_time_minutes, professional.is_active)

    # Return the updated professional info
    return updated_pro

# DELETE a professional (deactivated)
@router.delete("/professionals/{id}", status_code=200)
async def delete_professional(id: int, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the owner of the organization which the professional is linked to
    is_owner = await search_user_by_id(user_id)
    professional = await search_professional_by_id(id)

    # Check if professional exists
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional["organization_id"]) or is_owner["organization_id"] != professional["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, change the professional is_active to false
    is_deleted = await change_is_active(id, False)

    if is_deleted:
        success_dict = {
            "message": "Professional has been successfully deactivated."
        }
        return success_dict

# WORKING HOURS Related routes
# CREATE a professionals working hours
@router.post("/professionals/{id}/working-hours")
async def create_working_hour(id: int, workinghours: WorkingHoursCreate, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the owner of the organization the professional is linked to
    is_owner = await search_user_by_id(user_id)
    professional = await search_professional_by_id(id)
    organization = await search_organization_by_id(professional["organization_id"])

    # Check if the professional exists, if not, return 404
    if not professional:
        return HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional["organization_id"]) or is_owner["organization_id"] != professional["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Check to see if the WorkingHours input is within the organizations max and min work time
    # Convert timedelta to time if needed (UTC 0 for now)
    min_time = organization["min_work_time"]
    max_time = organization["max_work_time"]

    if isinstance(min_time, timedelta):
        min_time = (datetime.min.replace(tzinfo=timezone.utc) + min_time).time()

    if isinstance(max_time, timedelta):
        max_time = (datetime.min.replace(tzinfo=timezone.utc) + max_time).time()

    # Check to see if the WorkingHours input is within the organizations max and min work time
    # start_time verification
    if workinghours.start_time < min_time or workinghours.start_time > max_time:
        raise HTTPException(status_code=422, detail="Professional's start time can't be earlier than the time the organization opens or after the organization closes.")

    # end_time verification
    if workinghours.end_time > max_time or workinghours.end_time < min_time:
        raise HTTPException(status_code=422, detail="Professional's end time can't be earlier than the time the organization opens or after the organizationc closes.")

    # Else, create the working hours for the professional
    created_wk = await create_working_hours(id, workinghours.weekday, workinghours.start_time,
                                            workinghours.end_time, workinghours.is_active)

    # Return success message
    if created_wk:
        success_dict = {
            "message": f"Working hour successfully created. WkID = {created_wk}, ProfessionalID = {id}."
        }

        return success_dict

# READ all working hours of a professional (public route)
@router.get("/professionals/{professional_id}/working-hours", status_code=200)
async def get_working_hours_by_professional(professional_id: int, user_id: int = Depends(get_current_user_optional)):
    # Check if the professional exists
    is_exist = await search_professional_by_id(professional_id)

    # If it doesn't, return 404
    if not is_exist:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # Else, get all working hours registered under a professional
    registered_wks = await list_working_hours_by_professional(professional_id)

    # Return wks list
    return registered_wks

# UPDATE a existing working hour
@router.patch("/professionals/{professional_id}/working-hours/{id}", status_code=200)
async def update_working_hour(professional_id: int, id: int, workinghours: WorkingHoursUpdate, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the owner of the organization the professional is linked to
    is_owner = await search_user_by_id(user_id)
    professional = await search_professional_by_id(professional_id)
    organization = await search_organization_by_id(professional["organization_id"])

    # Check if the professional exists, if not, return 404
    if not professional:
        return HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional["organization_id"]) or is_owner["organization_id"] != professional["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Check to see if the WorkingHours input is within the organizations max and min work time
    # Convert timedelta to time if needed (UTC 0 for now)
    min_time = organization["min_work_time"]
    max_time = organization["max_work_time"]

    if isinstance(min_time, timedelta):
        min_time = (datetime.min.replace(tzinfo=timezone.utc) + min_time).time()

    if isinstance(max_time, timedelta):
        max_time = (datetime.min.replace(tzinfo=timezone.utc) + max_time).time()

    # Check to see if the WorkingHours input is within the organizations max and min work time
    # start_time verification
    if workinghours.start_time < min_time or workinghours.start_time > max_time:
        raise HTTPException(status_code=422, detail="Professional's start time can't be earlier than the time the organization opens or after the organization closes.")

    # end_time verification
    if workinghours.end_time > max_time or workinghours.end_time < min_time:
        raise HTTPException(status_code=422, detail="Professional's end time can't be earlier than the time the organization opens or after the organizationc closes.")

    # Update the working hour information
    updated_wk = await update_working_hours(id, workinghours.weekday, workinghours.start_time, workinghours.end_time, workinghours.is_active)

    # Return the updated working hour info
    return updated_wk

# BLACKOUTS related routes
# CREATE a blackout (professional-only)
@router.post("/professionals/{id}/blackouts", status_code=201)
async def create_blackout(id: int, blackout: BlackoutCreate, user_id: int = Depends(verify_user_token)):
    # Verify if the professional exists
    professional = await search_professional_by_id(id)

    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # Verify if the current user is the professional
    if professional["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Check if the start and end time for the blackout are greater than today
    today = datetime.now(timezone.utc)

    # Convert dates to UTC 0 to check without any naive to non-naive errors
    start_at = blackout.start_at.replace(tzinfo=timezone.utc)
    end_at = blackout.end_at.replace(tzinfo=timezone.utc)

    if start_at < today or end_at < today:
        raise HTTPException(status_code=422, detail="The start or end date for the blackout must be from today onwards.")

    # Else, create blackout
    recent_blackout_id = await create_blackouts(id, blackout.start_at, blackout.end_at, blackout.reason)

    # Return success message
    if recent_blackout_id:
        success_dict = {
            "message": f"Blackout successfully created for professional of id {id}. BlackoutID = {recent_blackout_id}"
        }

        return success_dict

# READ all blackouts of a professional
@router.get("/professionals/{id}/blackouts", status_code=200)
async def get_blackouts_by_professional(id: int, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the owner of the organization the professional is linked to
    is_owner = await search_user_by_id(user_id)
    professional = await search_professional_by_id(id)

    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional["organization_id"]) or is_owner["organization_id"] != professional["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, get all blackouts registered by the professional
    registered_blackouts = await list_blackouts_by_professional(id)

    # Return
    return registered_blackouts

# READ a blackout of id 'id'
@router.get("/professionals/blackouts/{id}", status_code=200)
async def get_blackout(id: int, user_id: int = Depends(verify_user_token)):
    # Check if the current user is the owner of the organization the professional is linked to
    blackout = await search_blackout_by_id(id)

    # Check if the blackout exists
    if not blackout:
        raise HTTPException(status_code=404, detail="Blackout not found or doesn't exist.")

    # Get current user information and professional information for owner verification
    is_owner = await search_user_by_id(user_id)
    professional = await search_professional_by_id(blackout["professional_id"])

    # If the owner conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional["organization_id"]) or is_owner["organization_id"] != professional["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, return the blackout
    return blackout

# PROFESSIONAL-PROCEDURE RELATIONS ROUTES
# CREATE professional-procedure relations
@router.post("/professionals/{id}/procedures", status_code=201)
async def create_pp_relation(id: int, pp: ProfessionalProcedureCreate, user_id: int = Depends(verify_user_token)):
    # Get current user information and professional information for owner verification
    is_owner = await search_user_by_id(user_id)
    professional = await search_professional_by_id(id)

    # If professional doesn't exist, return 404
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional["organization_id"]) or is_owner["organization_id"] != professional["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, create a professional-procedure relation
    is_created = await create_professional_procedure(pp.organization_id, id, pp.procedure_id, pp.is_active)

    if is_created:
        success_dict = {
            "message": f"Professional-Procedure link successfully created. Professional {id} have procedure {pp.procedure_id} linked to it."
        }
        return success_dict
# READ all procedures offered by a professional (public route)
@router.get("/professionals/{id}/procedures", status_code=200)
async def get_procedures_by_professionals(id: int, user_id: int = Depends(get_current_user_optional)):
    # Check if professional exists
    professional_exists = await search_professional_by_id(id)
    
    # If it doesn't, return 404
    if not professional_exists:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # Get organization of the professional
    organization_id = professional_exists["organization_id"]

    # Get all procedures made by this
    registered_pps = await list_professional_procedures(organization_id, id, None)

    return registered_pps

# DELETE a professional-procedure link (deactivate)
@router.delete("/professionals/{id}/procedures/{procedure_id}", status_code=200)
async def delete_professional_procedure(id: int, procedure_id: int, organization_id: int,user_id: int = Depends(verify_user_token)):
    # Check if the current user is the owner of the professional's organization and owner of the procedure's organization
    is_owner = await search_user_by_id(user_id)
    professional = await search_professional_by_id(id)
    procedure = await search_procedure_by_id(procedure_id)

    # If professional doesn't exist, return 404
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if (is_owner["role"] != "OWNER" and is_owner["organization_id"] == professional["organization_id"]) or (is_owner["organization_id"] != professional["organization_id"]) or is_owner["organization_id"] != procedure["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, deactivate the link
    is_deleted = await change_pp_is_active(organization_id, id, procedure_id, False)

    if is_deleted:
        success_dict = {
            "message": f"Successfully deactivated link between professional {id} and procedure {procedure_id}."
        }
        return success_dict