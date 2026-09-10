from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.schemas.schemas import AppointmentCreate, AppointmentUpdate
from app.api.v1.services.appointment_service import (
    appointment_canceled,
    create_appointment,
    list_appointments_by_organization,
    search_appointment_by_id,
    update_appointments,
)
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.permission_service import is_root
from app.api.v1.services.procedure_service import search_procedure_by_id
from app.api.v1.services.professional_service import (
    search_professional_by_id,
)

# Configure router
router = APIRouter(prefix="/v1/root")

@router.post("/appointments", status_code=201)
async def create_appointment_route(appointment: AppointmentCreate, user_id: int = Depends(verify_user_token)):
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
                                                          appointment.end_at,
                                                          appointment.status,
                                                          appointment.notes)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if created_appointment_id:
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
async def update_appointment(id: int, appointment: AppointmentUpdate, user_id: int = Depends(verify_user_token)):
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

    # Else, update the appointment and return it
    try:
        updated_appointment = await update_appointments(id, organization["id"], appointment.customer_id,
                                                        appointment.professional_id, appointment.procedure_id,
                                                        appointment.start_at, appointment.end_at,
                                                        appointment.status, appointment.notes
                                                        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return updated_appointment

@router.delete("/appointments/{id}", status_code=200)
async def cancel_appointment(id: int, user_id: int = Depends(verify_user_token)):
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
        success_dict = {
            "message": f"ROOT: Appointment {id} successfully canceled."
        }
        return success_dict