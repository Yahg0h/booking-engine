"""
Routes for managing appointments.
"""
import logging

logger = logging.getLogger(__name__)

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import AppointmentCreate, AppointmentUpdate
from app.api.v1.services.appointment_service import (
    appointment_canceled,
    check_appointment_access,
    create_appointment,
    list_appointments_filtered,
    search_appointment_by_id,
    update_appointments,
)
from app.api.v1.services.audit_service import get_ip_from_request, log_action
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.customer_service import update_customer_last_appointment
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.organization_settings_service import get_organization_settings
from app.api.v1.services.procedure_service import search_procedure_by_id
from app.api.v1.services.professional_service import (
    search_professional_by_id,
)
from app.rate_limiter import limiter

# Configure router
router = APIRouter(prefix="/v1")

@router.post("/appointments", status_code=201)
@limiter.limit("20/minute")
async def create_appointment_route(request: Request, appointment: AppointmentCreate, user_id: int = Depends(verify_user_token)):
    """
    Creates a new appointment.

    Args:
        request: The FastAPI request object
        appointment: The appointment creation schema
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message with the created appointment ID

    Raises:
        HTTPException: If organization, procedure or professional is not found, if the date is invalid, or if access is denied
        HTTPException: If there is a conflict creating the appointment
    """
    # Check if the org, customer, professional, procedure exists
    organization = await search_organization_by_id(appointment.organization_id)
    procedure = await search_procedure_by_id(appointment.procedure_id)
    professional = await search_professional_by_id(appointment.professional_id)

    if not organization or not procedure or not professional:
        raise HTTPException(status_code=404, detail="Organization, procedure or professional not found. Please retry.")

    # Verify if the date input is lesser than today
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # If it is, raise 422
    if appointment.start_at and appointment.start_at < now:
        raise HTTPException(status_code=422, detail="The appointment date must be from today onwards.")

    # Check access
    if not await check_appointment_access(user_id, appointment.organization_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, create a appointment
    try:
        created_appointment_id = await create_appointment(appointment.organization_id,
                                                          appointment.customer_id,
                                                          appointment.professional_id,
                                                          appointment.procedure_id,
                                                          appointment.start_at,
                                                          appointment.status,
                                                          appointment.end_at,
                                                          appointment.notes)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if created_appointment_id:
        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Appointment created: id={created_appointment_id}, "
            f"professional_id={appointment.professional_id}, "
            f"customer_id={appointment.customer_id}, "
            f"organization_id={appointment.organization_id}, "
            f"start_at={appointment.start_at.isoformat()}"
        )

        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "organization_id": appointment.organization_id,
            "customer_id": appointment.customer_id,
            "professional_id": appointment.professional_id,
            "procedure_id": appointment.procedure_id,
            "start_at": appointment.start_at,
            "status": appointment.status,
            "end_at": appointment.end_at,
            "notes": appointment.notes
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Log action
        await log_action(
            organization_id=appointment.organization_id,
            actor_user_id=user_id,
            action='CREATE',
            entity_type='APPOINTMENT',
            entity_id=created_appointment_id,
            old_values=None,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        success_dict = {
            "message": f"Appointment ID {created_appointment_id} successfully created."
        }
        return success_dict

@router.get("/appointments", status_code=200)
@limiter.limit("50/minute")
async def list_appointments(request: Request, organization_id: int,
                            customer_id: int | None = None,
                            professional_id: int | None = None,
                            procedure_id: int | None = None,
                            start_at: datetime | None = None,
                            end_at: datetime | None = None,
                            status: str | None = None,
                            user_id: int = Depends(verify_user_token)):
    """
    Lists all registered appointments based on the provided filters.

    Args:
        organization_id: The ID of the organization
        customer_id: The ID of the customer (optional)
        professional_id: The ID of the professional (optional)
        procedure_id: The ID of the procedure (optional)
        start_at: The start date and time filter (optional)
        end_at: The end date and time filter (optional)
        status: The status filter (optional)
        user_id: The ID of the authenticated user

    Returns:
        list: A list of appointments matching the filters

    Raises:
        HTTPException: If access is denied
    """
    # Check access
    if not await check_appointment_access(user_id, organization_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, list all registered appointments in the organization/ mudar
    registered_appointments = await list_appointments_filtered(organization_id, customer_id, professional_id,
                                                               procedure_id, start_at, end_at, status)

    return registered_appointments

@router.get("/appointments/{id}", status_code=200)
@limiter.limit("50/minute")
async def get_appointment(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    """
    Retrieves information about a specific appointment by ID.

    Args:
        id: The ID of the appointment
        user_id: The ID of the authenticated user

    Returns:
        dict: The appointment information

    Raises:
        HTTPException: If the appointment is not found or if access is denied
    """
    # Check if the appointment exists
    appointment = await search_appointment_by_id(id)

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found or doesn't exist.")

    # Get the organization's info in which the appointment is registered into
    professional = await search_professional_by_id(appointment["professional_id"])
    organization = await search_organization_by_id(professional["organization_id"])

    # Check access
    if not await check_appointment_access(user_id, organization["id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, return the appointment information
    return appointment

@router.patch("/appointments/{id}", status_code=200)
@limiter.limit("20/minute")
async def update_appointment(request: Request, id: int, appointment: AppointmentUpdate, user_id: int = Depends(verify_user_token)):
    """
    Updates the information of an existing appointment.

    Args:
        request: The FastAPI request object
        id: The ID of the appointment
        appointment: The appointment update schema
        user_id: The ID of the authenticated user

    Returns:
        dict: The updated appointment information

    Raises:
        HTTPException: If the appointment, organization, procedure or professional is not found, if the date is invalid, or if access is denied
        HTTPException: If there is a conflict updating the appointment
    """
    # Check if the appointment exists
    is_exist = await search_appointment_by_id(id)

    if not is_exist:
        raise HTTPException(status_code=404, detail="Appointment not found or doesn't exist.")

    # Check if the org, customer, professional, procedure exists
    organization = await search_organization_by_id(is_exist["organization_id"])
    procedure = await search_procedure_by_id(appointment.procedure_id)
    professional = await search_professional_by_id(appointment.professional_id)

    if not organization or not procedure or not professional:
        raise HTTPException(status_code=404, detail="Organization, procedure or professional not found. Please retry.")

    # Verify if the date input is lesser than today
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # If it is, raise 422
    if appointment.start_at and appointment.start_at < now:
        raise HTTPException(status_code=422, detail="The appointment date must be from today onwards.")

    # Check access
    if not await check_appointment_access(user_id, organization["id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, update the appointment
    try:
        updated_appointment = await update_appointments(id, organization["id"], appointment.customer_id,
                                                        appointment.professional_id, appointment.procedure_id,
                                                        appointment.start_at, appointment.end_at,
                                                        appointment.status, appointment.notes
                                                        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # ==== AUDIT LOGS ENTRY ====
    # Get organization id
    appointment_organization_id = int(is_exist["organization_id"]) if is_exist["organization_id"] else None

    # Add new values to a dict and log action
    old_values = is_exist
    new_values = {"organization_id": appointment_organization_id}
    if appointment.customer_id is not None: new_values["customer_id"] = appointment.customer_id
    if appointment.professional_id is not None: new_values["professional_id"] = appointment.professional_id
    if appointment.procedure_id is not None: new_values["procedure_id"] = appointment.procedure_id
    if appointment.start_at is not None: new_values["start_at"] = appointment.start_at
    if appointment.end_at is not None: new_values["end_at"] = appointment.end_at
    if appointment.status is not None: new_values["status"] = appointment.status
    if appointment.notes is not None: new_values["notes"] = appointment.notes

    # Get IP Address
    ip_address = get_ip_from_request(request)

    # Log action
    await log_action(
        organization_id=appointment_organization_id,
        actor_user_id=user_id,
        action='UPDATE',
        entity_type='APPOINTMENT',
        entity_id=id,
        old_values=old_values,
        new_values=new_values,
        metadata={"source": "api", "version": "1.0"},
        ip_address=ip_address
    )
    # ==== END OF AUDIT LOGS ENTRY ====

    # ==== STRUCTURED LOGGING ====
    logger.info(
        f"Appointment updated: id={id}, "
        f"org_id={appointment_organization_id}, "
        f"field_changed={list(new_values.keys())}"
    )

    # If the appointment has been completed, update the customers 'last_appointment_at' info
    if appointment.status == "COMPLETED":
        await update_customer_last_appointment(appointment.customer_id, now)

    # Return the updated appointment info
    return updated_appointment

@router.delete("/appointments/{id}", status_code=200)
@limiter.limit("30/minute")
async def cancel_appointment(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    """
    Cancels an existing appointment.

    Args:
        request: The FastAPI request object
        id: The ID of the appointment
        user_id: The ID of the authenticated user

    Returns:
        dict: A success message

    Raises:
        HTTPException: If the appointment, organization, procedure or professional is not found, or if access is denied
    """
    # Check if the appointment exists
    appointment = await search_appointment_by_id(id)

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found or doesn't exist.")

    # Check if the org, customer, professional, procedure exists
    organization = await search_organization_by_id(appointment["organization_id"])
    procedure = await search_procedure_by_id(appointment["procedure_id"])
    professional = await search_professional_by_id(appointment["professional_id"])

    if not organization or not procedure or not professional:
        raise HTTPException(status_code=404, detail="Organization, procedure or professional not found. Please retry.")

    # Check access
    if not await check_appointment_access(user_id, organization["id"]):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Verify whether the cancellation policy is being adhered to
    settings = await get_organization_settings(appointment["organization_id"])

    if settings is None:
        raise HTTPException(status_code=409, detail="Organization settings are not configured.")

    now = datetime.now(timezone.utc)
    appointment_start = appointment["start_at"]
    if appointment_start.tzinfo is None:
        appointment_start = appointment_start.replace(tzinfo=timezone.utc)

    time_until_appointment = (appointment_start - now).total_seconds() / 3600

    if time_until_appointment < settings["cancellation_buffer_hours"]:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot cancel appointment less than {settings['cancellation_buffer_hours']} hours before the scheduled time."
        )

    # Cancel the appointment
    is_canceled = await appointment_canceled(id)

    if is_canceled:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        old_values = appointment
        new_values = {
            "status": "CANCELLED"
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)

        # Get organization id
        appointment_organization_id = int(appointment["organization_id"]) if appointment["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=appointment_organization_id,
            actor_user_id=user_id,
            action='DELETE',
            entity_type='APPOINTMENT',
            entity_id=id,
            old_values=old_values,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Appointment deleted: id={id}, "
            f"org_id={appointment_organization_id}"
        )

        success_dict = {
            "message": f"Appointment {id} successfully canceled."
        }
        return success_dict