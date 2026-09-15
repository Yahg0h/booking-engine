import logging

logger = logging.getLogger(__name__)

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import AppointmentCreate, AppointmentUpdate
from app.api.v1.services.appointment_service import (
    appointment_canceled,
    create_appointment,
    list_appointments_by_organization,
    search_appointment_by_id,
    update_appointments,
)
from app.api.v1.services.audit_service import get_ip_from_request, log_action
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.customer_service import update_customer_last_appointment
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.permission_service import is_root
from app.api.v1.services.procedure_service import search_procedure_by_id
from app.api.v1.services.professional_service import (
    search_professional_by_id,
)

# Configure router
router = APIRouter(prefix="/v1/root")

@router.post("/appointments", status_code=201)
async def create_appointment_route(request: Request, appointment: AppointmentCreate, user_id: int = Depends(verify_user_token)):
    # Check if the org, customer, professional, procedure exists
    organization = await search_organization_by_id(appointment.organization_id)
    procedure = await search_procedure_by_id(appointment.procedure_id)
    professional = await search_professional_by_id(appointment.professional_id)

    if not organization or not procedure or not professional:
        raise HTTPException(status_code=404, detail="Organization, procedure or professional not found. Please retry.")

    # Verify if the date input is lesser than today
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # If it is, raise 422
    if appointment.start_at < now:
        raise HTTPException(status_code=422, detail="The appointment date must be from today onwards.")

    # Check access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

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
            f"ROOT: Appointment created: id={created_appointment_id}, "
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
            "message": f"ROOT: Appointment ID {created_appointment_id} successfully created."
        }
        return success_dict

@router.get("/appointments", status_code=200)
async def list_appointments(organization_id: int, user_id: int = Depends(verify_user_token)):
    # Check access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, list all registered appointments in the organization
    registered_appointments = await list_appointments_by_organization(organization_id)

    return registered_appointments

@router.get("/appointments/{id}", status_code=200)
async def get_appointment(id: int, user_id: int = Depends(verify_user_token)):
    # Check if the appointment exists
    appointment = await search_appointment_by_id(id)

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found or doesn't exist.")

    # Check access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, return the appointment information
    return appointment

@router.patch("/appointments/{id}", status_code=200)
async def update_appointment(request: Request, id: int, appointment: AppointmentUpdate, user_id: int = Depends(verify_user_token)):
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
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

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
        f"ROOT: Appointment updated: id={id}, "
        f"org_id={appointment_organization_id}, "
        f"field_changed={list(new_values.keys())}"
    )

    # If the appointment has been completed, update the customers 'last_appointment_at' info
    if appointment.status == "COMPLETED":
        await update_customer_last_appointment(appointment.customer_id, now)

    # Return the updated appointment info
    return updated_appointment

@router.delete("/appointments/{id}", status_code=200)
async def cancel_appointment(request: Request, id: int, user_id: int = Depends(verify_user_token)):
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
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

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
            f"ROOT: Appointment deleted: id={id}, "
            f"org_id={appointment_organization_id}"
        )

        success_dict = {
            "message": f"ROOT: Appointment {id} successfully canceled."
        }
        return success_dict