"""
Routes for managing booking availability.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.v1.services.availability_service import availability_service
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.procedure_service import search_procedure_by_id
from app.api.v1.services.professional_service import search_professional_by_id

# Configure router
router = APIRouter(prefix="/v1")

@router.get("/availability", status_code=200)
async def booking_availability(organization_id: int, professional_id: int, procedure_id: int, date: date):
    """
    Checks for available booking slots on a specific date.

    Args:
        organization_id: The ID of the organization
        professional_id: The ID of the professional
        procedure_id: The ID of the procedure
        date: The date to check for availability

    Returns:
        list: A list of available slots for the given date

    Raises:
        HTTPException: If the organization, professional or procedure is not found, or if the date is invalid
    """
    # Check if the organization, professional and procedure exists
    organization = await search_organization_by_id(organization_id)
    professional = await search_professional_by_id(professional_id)
    procedure = await search_procedure_by_id(procedure_id)

    # If any of them doesn't exist, return 404
    if not organization or not professional or not procedure:
        raise HTTPException(status_code=404, detail="Organization, professional or procedure not found. Please retry.")

    # Verify if the date input is lesser than today
    now = datetime.now(timezone.utc).date()

    # If it is, raise 422
    if date < now:
        raise HTTPException(status_code=422, detail="The appointment date must be from today onwards.")

    # Call availability service and return all available slots
    try:
        available_slots = await availability_service(organization_id, professional_id, procedure_id, date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return available_slots