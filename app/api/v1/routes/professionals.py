"""
Routes for managing professionals.
"""
import logging

logger = logging.getLogger(__name__)

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import (
    BlackoutCreate,
    ProfessionalCreate,
    ProfessionalProcedureCreate,
    ProfessionalUpdate,
    WorkingHoursCreate,
    WorkingHoursUpdate,
)
from app.api.v1.services.audit_service import get_ip_from_request, log_action
from app.api.v1.services.auth_service import (
    get_current_user_optional,
    verify_user_token,
)
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.organization_settings_service import get_organization_settings
from app.api.v1.services.permission_service import is_root
from app.api.v1.services.procedure_service import (
    change_pp_is_active,
    create_professional_procedure,
    list_professional_procedures,
    search_procedure_by_id,
)
from app.api.v1.services.professional_service import (
    approve_blackout,
    change_is_active,
    check_existing_weekday,
    check_professional_access,
    create_blackouts,
    create_professionals,
    create_working_hours,
    list_all_professionals,
    list_blackouts_by_professional,
    list_professionals_by_org,
    list_working_hours_by_professional,
    reject_blackout,
    search_blackout_by_id,
    search_professional_by_id,
    search_working_hour_by_id,
    update_professional,
    update_working_hours,
)
from app.api.v1.services.user_service import search_user_by_id
from app.rate_limiter import limiter

# Configure router
router = APIRouter(prefix="/v1")

# CREATE professional
@router.post("/professionals", status_code=201)
@limiter.limit("30/minute")
async def create_professional_route(request: Request, professional: ProfessionalCreate, user_id: int = Depends(verify_user_token)):
    """
    Creates a new professional.

    Args:
        request: The FastAPI request object
        professional: The professional creation schema
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message with the created professional ID

    Raises:
        HTTPException: If access is denied
    """
    # Check if the current user is a OWNER of the selected professional organization or root; If the conditions fail, return 403
    if not await check_professional_access(user_id, professional.organization_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, create the professional
    created = await create_professionals(professional.organization_id,
                                            professional.user_id,
                                            professional.name,
                                            professional.buffer_time_minutes,
                                            professional.is_active)

    # ==== AUDIT LOGS ENTRY ====
    # Add new values to a dict and log action
    new_values = {
        "organization_id": professional.organization_id,
        "user_id": professional.user_id,
        "name": professional.name,
        "buffer_time_minutes": professional.buffer_time_minutes,
        "is_active": professional.is_active
    }

    # Get IP Address
    ip_address = get_ip_from_request(request)

    # Log action
    await log_action(
        organization_id=professional.organization_id,
        actor_user_id=user_id,
        action='CREATE',
        entity_type='PROFESSIONAL',
        entity_id=created,
        old_values=None,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====
    
    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"Professional created: id={created}, "
        f"org_id={professional.organization_id}"
    )

    # Return success message
    success_dict = {
        "message": f"Professional successfully created. OrgID = {professional.organization_id}, PfID = {created}, UserID = {professional.user_id}."
    }

    return success_dict

# READ all professionals in a organization
@router.get("/professionals", status_code=200)
@limiter.limit("30/minute")
async def get_professionals(request: Request, organization_id: int, is_active: bool = True, user_id: int = Depends(verify_user_token)):
    """
    Lists all professionals in an organization.

    Args:
        organization_id: The ID of the organization
        is_active: The status filter
        user_id: The ID of the authenticated user

    Returns:
        list: A list of registered professionals

    Raises:
        HTTPException: If access is denied
    """
    # Check if the current user is a OWNER of the selected organization or root; If the conditions fail, return 403
    if not await check_professional_access(user_id, organization_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Else, get all professionals registered under this organization
    professionals = await list_professionals_by_org(organization_id, is_active=is_active)

    # Return list
    return professionals

# READ all professionals registered across all registered organizations (root-only)
@router.get("/professionals/all", status_code=200)
@limiter.limit("30/minute")
async def get_all_professionals(request: Request, is_active: bool = True, user_id: int = Depends(verify_user_token)):
    """
    Lists all professionals registered across all organizations (root-only).

    Args:
        is_active: The status filter
        user_id: The ID of the authenticated user

    Returns:
        list: A list of all registered professionals

    Raises:
        HTTPException: If access is denied (not root)
    """
    # Check if the current user is a root account; If it isn't, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Else, get all registered professionals registered
    professionals = await list_all_professionals(is_active=is_active)

    # Return list
    return professionals

# READ information of a specific professional (public route)
@router.get("/professionals/{id}", status_code=200)
@limiter.limit("30/minute")
async def get_professional(request: Request, id: int, user_id: int = Depends(get_current_user_optional)):
    """
    Retrieves public information of a specific professional.

    Args:
        id: The ID of the professional
        user_id: The ID of the authenticated user (optional)

    Returns:
        dict: The public professional information

    Raises:
        HTTPException: If the professional is not found
    """
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
@limiter.limit("30/minute")
async def update_professional_route(request: Request, id: int, professional: ProfessionalUpdate, user_id: int = Depends(verify_user_token)):
    """
    Updates a professional's information.

    Args:
        request: The FastAPI request object
        id: The ID of the professional
        professional: The professional update schema
        user_id: The ID of the authenticated user

    Returns:
        dict: The updated professional information

    Raises:
        HTTPException: If the professional is not found or if access is denied
    """
    # Check if the current user is a OWNER of the organization which the professional is linked to or root
    professional_db = await search_professional_by_id(id)

    # Check if the professional exists
    if not professional_db:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the access conditions fail, return 403
    if not await check_professional_access(user_id, professional_db["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, update the professional info
    updated_pro = await update_professional(id, professional.organization_id, professional.name, professional.user_id,
                                            professional.buffer_time_minutes, professional.is_active)

    # ==== AUDIT LOGS ENTRY ====
    # Add new values to a dict and log action
    old_values = professional_db
    new_values = {}
    if professional.organization_id is not None: new_values["organization_id"] = professional.organization_id
    if professional.name is not None: new_values["name"] = professional.name
    if professional.user_id is not None: new_values["user_id"] = professional.user_id
    if professional.buffer_time_minutes is not None: new_values["buffer_time_minutes"] = professional.buffer_time_minutes
    if professional.is_active is not None: new_values["is_active"] = professional.is_active

    # Get IP Address
    ip_address = get_ip_from_request(request)

    # Get user organization_id
    user_organization_id = int(professional_db["organization_id"]) if professional_db["organization_id"] else None

    # Log action
    await log_action(
        organization_id=user_organization_id,
        actor_user_id=user_id,
        action='UPDATE',
        entity_type='PROFESSIONAL',
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
        f"org_id={user_organization_id}, "
        f"field_changed={list(new_values.keys())}"
    )

    # Return the updated professional info
    return updated_pro

# DELETE a professional (deactivated)
@router.delete("/professionals/{id}", status_code=200)
@limiter.limit("30/minute")
async def delete_professional(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    """
    Deactivates a professional.

    Args:
        request: The FastAPI request object
        id: The ID of the professional
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message

    Raises:
        HTTPException: If the professional is not found or if access is denied
    """
    # Check if the current user is the owner of the organization which the professional is linked to or root
    professional = await search_professional_by_id(id)

    # Check if professional exists
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the access conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, change the professional is_active to false
    is_deleted = await change_is_active(id, False)

    if is_deleted:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        old_values = professional
        new_values = {
            "is_active": False
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get user organization_id
        user_organization_id = int(professional["organization_id"]) if professional["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=user_organization_id,
            actor_user_id=user_id,
            action='DELETE',
            entity_type='PROFESSIONAL',
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
            f"org_id={user_organization_id}"
        )

        success_dict = {
            "message": "Professional has been successfully deactivated."
        }
        return success_dict

# ==========================================
# WORKING HOUR RELATED ROUTES
# ==========================================
# CREATE a professionals working hours
@router.post("/professionals/{id}/working-hours")
@limiter.limit("30/minute")
async def create_working_hour(request: Request, id: int, workinghours: WorkingHoursCreate, user_id: int = Depends(verify_user_token)):
    """
    Creates working hours for a professional.

    Args:
        request: The FastAPI request object
        id: The ID of the professional
        workinghours: The working hours creation schema
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message with the created working hour ID

    Raises:
        HTTPException: If the professional is not found, if there are conflicts, or if access is denied
    """
    # Check if the current user is the owner of the organization the professional is linked to or root
    professional = await search_professional_by_id(id)
    organization = await search_organization_by_id(professional["organization_id"])

    # Check if the professional exists, if not, return 404
    if not professional:
        return HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Verify if the new working hour information isn't on a weekday that already has a working hour registered
    if await check_existing_weekday(workinghours.weekday, id):
        raise HTTPException(status_code=409, detail="A working hour record already exists for the selected day of the week.")

    # Verify if the professional can work on this day (organization must operate on this day)
    settings = await get_organization_settings(professional["organization_id"])

    if workinghours.weekday not in settings["operating_weekdays"]:
        raise HTTPException(
            status_code=422,
            detail=f"Professional cannot work on day {workinghours.weekday}. Organization operates on: {settings['operating_weekdays']}"
        )

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
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "weekday": workinghours.weekday,
            "start_time": workinghours.start_time,
            "end_time": workinghours.end_time,
            "is_active": workinghours.is_active
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get user organization_id
        user_organization_id = int(professional["organization_id"]) if professional["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=user_organization_id,
            actor_user_id=user_id,
            action='CREATE',
            entity_type='WORKING_HOUR',
            entity_id=created_wk,
            old_values=None,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Working Hour created: id={created_wk}, "
            f"org_id={user_organization_id}, "
            f"prof_id={id}, "
        )

        success_dict = {
            "message": f"Working hour successfully created. WkID = {created_wk}, ProfessionalID = {id}."
        }

        return success_dict

# READ all working hours of a professional (public route)
@router.get("/professionals/{professional_id}/working-hours", status_code=200)
@limiter.limit("30/minute")
async def get_working_hours_by_professional(request: Request, professional_id: int, is_active: bool = True, user_id: int = Depends(get_current_user_optional)):
    """
    Lists all working hours for a specific professional.

    Args:
        professional_id: The ID of the professional
        is_active: The status filter
        user_id: The ID of the authenticated user (optional)

    Returns:
        list: A list of registered working hours

    Raises:
        HTTPException: If the professional is not found
    """
    # Check if the professional exists
    is_exist = await search_professional_by_id(professional_id)

    # If it doesn't, return 404
    if not is_exist:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # Else, get all working hours registered under a professional
    registered_wks = await list_working_hours_by_professional(professional_id, is_active=is_active)

    # Return wks list
    return registered_wks

# UPDATE a existing working hour
@router.patch("/professionals/{professional_id}/working-hours/{id}", status_code=200)
@limiter.limit("30/minute")
async def update_working_hour(request: Request, professional_id: int, id: int, workinghours: WorkingHoursUpdate, user_id: int = Depends(verify_user_token)):
    """
    Updates the information of a working hour.

    Args:
        request: The FastAPI request object
        professional_id: The ID of the professional
        id: The ID of the working hour
        workinghours: The working hours update schema
        user_id: The ID of the authenticated user

    Returns:
        dict: The updated working hour information

    Raises:
        HTTPException: If the professional is not found, if there are conflicts, or if access is denied
    """
    # Check if the current user is the owner of the organization the professional is linked to or root
    professional = await search_professional_by_id(professional_id)
    organization = await search_organization_by_id(professional["organization_id"])

    # Check if the professional exists, if not, return 404
    if not professional:
        return HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Verify if the new working hour information isn't on a weekday that already has a working hour registered
    if await check_existing_weekday(workinghours.weekday, id):
        raise HTTPException(status_code=409, detail="A working hour record already exists for the selected day of the week.")

    # Verify if the professional can work on this day (organization must operate on this day)
    settings = await get_organization_settings(professional["organization_id"])

    if workinghours.weekday not in settings["operating_weekdays"]:
        raise HTTPException(
            status_code=422,
            detail=f"Professional cannot work on day {workinghours.weekday}. Organization operates on: {settings['operating_weekdays']}"
        )

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

    # ==== AUDIT LOGS ENTRY ====
    # Add new values to a dict and log action
    old_values = await search_working_hour_by_id(id)
    new_values = {}
    if workinghours.weekday is not None: new_values["weekday"] = workinghours.weekday
    if workinghours.start_time is not None: new_values["start_time"] = workinghours.start_time
    if workinghours.end_time is not None: new_values["end_time"] = workinghours.end_time
    if workinghours.is_active is not None: new_values["is_active"] = workinghours.is_active

    # Get IP Address
    ip_address = get_ip_from_request(request)

    # Get user organization_id
    user_organization_id = int(professional["organization_id"]) if professional["organization_id"] else None

    # Log action
    await log_action(
        organization_id=user_organization_id,
        actor_user_id=user_id,
        action='UPDATE',
        entity_type='WORKING_HOUR',
        entity_id=id,
        old_values=old_values,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====

    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"Working Hour updated: id={id}, "
        f"org_id={user_organization_id}, "
        f"prof_id={professional_id}, "
        f"start_at={new_values.get('start_at').isoformat() if 'start_at' in new_values else 'N/A'}, "
        f"end_at={new_values.get('end_at').isoformat() if 'end_at' in new_values else 'N/A'}, "
        f"field_changed={list(new_values.keys())}"
    )

    # Return the updated working hour info
    return updated_wk

# ==========================================
# BLACKOUT RELATED ROUTES
# ==========================================
# CREATE a blackout (professional-only)
@router.post("/professionals/{id}/blackouts", status_code=201)
@limiter.limit("30/minute")
async def create_blackout(request: Request, id: int, blackout: BlackoutCreate, user_id: int = Depends(verify_user_token)):
    """
    Creates a blackout for a professional.

    Args:
        request: The FastAPI request object
        id: The ID of the professional
        blackout: The blackout creation schema
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message with the created blackout ID

    Raises:
        HTTPException: If the professional is not found, if the dates are invalid, or if access is denied
    """
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
    recent_blackout_id = await create_blackouts(id, blackout.start_at, blackout.end_at, blackout.reason, "PENDING")

    # Return success message
    if recent_blackout_id:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "start_at": blackout.start_at,
            "end_at": blackout.end_at,
            "reason": blackout.reason
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get user organization_id
        user_organization_id = int(professional["organization_id"]) if professional["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=user_organization_id,
            actor_user_id=user_id,
            action='CREATE',
            entity_type='BLACKOUT',
            entity_id=recent_blackout_id,
            old_values=None,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Blackout created: id={recent_blackout_id}, "
            f"org_id={user_organization_id}, "
            f"prof_id={id}"
        )

        success_dict = {
            "message": f"Blackout successfully created for professional of id {id}. BlackoutID = {recent_blackout_id}"
        }

        return success_dict

# READ all blackouts of a professional
@router.get("/professionals/{id}/blackouts", status_code=200)
@limiter.limit("30/minute")
async def get_blackouts_by_professional(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    """
    Lists all blackouts for a specific professional.

    Args:
        id: The ID of the professional
        user_id: The ID of the authenticated user

    Returns:
        list: A list of registered blackouts

    Raises:
        HTTPException: If the professional is not found or if access is denied
    """
    # Check if the current user is the owner of the organization the professional is linked to or root
    professional = await search_professional_by_id(id)

    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, get all blackouts registered by the professional
    registered_blackouts = await list_blackouts_by_professional(id)

    # Return
    return registered_blackouts

# READ a blackout of id 'id'
@router.get("/professionals/blackouts/{id}", status_code=200)
@limiter.limit("30/minute")
async def get_blackout(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    """
    Retrieves information about a specific blackout.

    Args:
        id: The ID of the blackout
        user_id: The ID of the authenticated user

    Returns:
        dict: The blackout information

    Raises:
        HTTPException: If the blackout is not found or if access is denied
    """
    # Check if the current user is the owner of the organization the professional is linked to or root
    blackout = await search_blackout_by_id(id)

    # Check if the blackout exists
    if not blackout:
        raise HTTPException(status_code=404, detail="Blackout not found or doesn't exist.")

    # Get current user information and professional information for owner verification
    professional = await search_professional_by_id(blackout["professional_id"])

    # If the owner conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, return the blackout
    return blackout

@router.post("/blackouts/{id}/approve", status_code=200)
@limiter.limit("30/minute")
async def approve_blackout_route(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    """
    Approves a blackout.

    Args:
        request: The FastAPI request object
        id: The ID of the blackout
        user_id: The ID of the authenticated user

    Returns:
        dict: The updated blackout information

    Raises:
        HTTPException: If the blackout is not found or if access is denied
    """
    # Check if the current user is the owner of the organization the professional is linked to or root
    blackout = await search_blackout_by_id(id)

    # Check if the blackout exists
    if not blackout:
        raise HTTPException(status_code=404, detail="Blackout not found or doesn't exist.")

    # Get current user information and professional information for owner verification
    professional = await search_professional_by_id(blackout["professional_id"])

    # If the owner conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, approve blackout
    approved_blackout = await approve_blackout(id)

    if approved_blackout:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "status": "ACCEPTED"
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get user organization_id
        user_organization_id = int(professional["organization_id"]) if professional["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=user_organization_id,
            actor_user_id=user_id,
            action='UPDATE',
            entity_type='BLACKOUT',
            entity_id=id,
            old_values=blackout,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Blackout accepted: id={id}, "
            f"org_id={user_organization_id}"
        )

    return approved_blackout

@router.post("/blackouts/{id}/reject", status_code=200)
@limiter.limit("30/minute")
async def reject_blackout_route(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    """
    Rejects a blackout.

    Args:
        request: The FastAPI request object
        id: The ID of the blackout
        user_id: The ID of the authenticated user

    Returns:
        dict: The updated blackout information

    Raises:
        HTTPException: If the blackout is not found or if access is denied
    """
    # Check if the current user is the owner of the organization the professional is linked to or root
    blackout = await search_blackout_by_id(id)

    # Check if the blackout exists
    if not blackout:
        raise HTTPException(status_code=404, detail="Blackout not found or doesn't exist.")

    # Get current user information and professional information for owner verification
    professional = await search_professional_by_id(blackout["professional_id"])

    # If the owner conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, reject blackout
    rejected_blackout = await reject_blackout(id)

    if rejected_blackout:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "status": "REJECTED"
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get user organization_id
        user_organization_id = int(professional["organization_id"]) if professional["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=user_organization_id,
            actor_user_id=user_id,
            action='UPDATE',
            entity_type='BLACKOUT',
            entity_id=id,
            old_values=blackout,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Blackout rejected: id={id}, "
            f"org_id={user_organization_id}"
        )

    return rejected_blackout

# ==========================================
# PROFESSIONAL-PROCEDURES RELATIONS ROUTES
# ==========================================
# CREATE professional-procedure relations
@router.post("/professionals/{id}/procedures", status_code=201)
@limiter.limit("30/minute")
async def create_pp_relation(request: Request, id: int, pp: ProfessionalProcedureCreate, user_id: int = Depends(verify_user_token)):
    """
    Creates a link between a professional and a procedure.

    Args:
        request: The FastAPI request object
        id: The ID of the professional
        pp: The professional-procedure creation schema
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message

    Raises:
        HTTPException: If the professional is not found or if access is denied
    """
    # Get current user information and professional information for owner verification
    professional = await search_professional_by_id(id)

    # If professional doesn't exist, return 404
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, create a professional-procedure relation
    is_created = await create_professional_procedure(pp.organization_id, id, pp.procedure_id, pp.is_active)

    if is_created:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "organization_id": pp.organization_id,
            "procedure_id": pp.procedure_id,
            "is_active": pp.is_active
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get user organization_id
        user_organization_id = int(professional["organization_id"]) if professional["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=user_organization_id,
            actor_user_id=user_id,
            action='CREATE',
            entity_type='PROFESSIONAL_PROCEDURE',
            entity_id=None,
            old_values=None,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Professional-Procedure created, "
            f"org_id={user_organization_id}, "
            f"prof_id={id}"
            f"procedure_id={pp.procedure_id}"
        )

        success_dict = {
            "message": f"Professional-Procedure link successfully created. Professional {id} have procedure {pp.procedure_id} linked to it."
        }
        return success_dict

# READ all procedures offered by a professional (public route)
@router.get("/professionals/{id}/procedures", status_code=200)
@limiter.limit("30/minute")
async def get_procedures_by_professionals(request: Request, id: int, is_active: bool = True, user_id: int = Depends(get_current_user_optional)):
    """
    Lists all procedures offered by a specific professional.

    Args:
        id: The ID of the professional
        is_active: The status filter
        user_id: The ID of the authenticated user (optional)

    Returns:
        list: A list of procedures offered by the professional

    Raises:
        HTTPException: If the professional is not found
    """
    # Check if professional exists
    professional_exists = await search_professional_by_id(id)
    
    # If it doesn't, return 404
    if not professional_exists:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # Get organization of the professional
    organization_id = professional_exists["organization_id"]

    # Get all procedures made by this
    registered_pps = await list_professional_procedures(organization_id, id, None, is_active=is_active)

    return registered_pps

# DELETE a professional-procedure link (deactivate)
@router.delete("/professionals/{id}/procedures/{procedure_id}", status_code=200)
@limiter.limit("30/minute")
async def delete_professional_procedure(request: Request, id: int, procedure_id: int, organization_id: int,user_id: int = Depends(verify_user_token)):
    """
    Deactivates a link between a professional and a procedure.

    Args:
        request: The FastAPI request object
        id: The ID of the professional
        procedure_id: The ID of the procedure
        organization_id: The ID of the organization
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message

    Raises:
        HTTPException: If the professional is not found or if access is denied
    """
    # Check if the current user is the owner of the professional's organization and owner of the procedure's organization
    owner = await search_user_by_id(user_id)
    professional = await search_professional_by_id(id)
    procedure = await search_procedure_by_id(procedure_id)

    # If professional doesn't exist, return 404
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found or doesn't exist.")

    # If the owner conditions fail, return 403
    if not await check_professional_access(user_id, professional["organization_id"]) or owner["organization_id"] != procedure["organization_id"]:
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, deactivate the link
    is_deleted = await change_pp_is_active(organization_id, id, procedure_id, False)

    if is_deleted:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        from app.api.v1.services.procedure_service import (
            search_professional_procedure_unique,
        )
        old_values = await search_professional_procedure_unique(organization_id, id, procedure_id, None)
        new_values = {
            "is_active": False
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get user organization_id
        user_organization_id = int(professional["organization_id"]) if professional["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=user_organization_id,
            actor_user_id=user_id,
            action='DELETE',
            entity_type='PROFESSIONAL_PROCEDURE',
            entity_id=None,
            old_values=old_values,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Professional-Procedure link deleted, "
            f"org_id={user_organization_id}, "
            f"prof_id={id}"
            f"procedure_id={procedure_id}"
        )

        success_dict = {
            "message": f"Successfully deactivated link between professional {id} and procedure {procedure_id}."
        }
        return success_dict