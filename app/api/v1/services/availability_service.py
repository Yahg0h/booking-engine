"""
Service logic for calculating professional availability slots.
"""

from datetime import date, datetime, time, timedelta, timezone

from app.api.v1.services.appointment_service import list_appointments_by_time_frame
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.organization_settings_service import get_organization_settings
from app.api.v1.services.procedure_service import (
    search_procedure_by_id,
    search_professional_procedure_unique,
)
from app.api.v1.services.professional_service import (
    list_active_working_hours_by_professional,
    list_blackouts_by_professional,
    search_professional_by_id,
)


def _timedelta_to_time(td: timedelta) -> time:
    """Convert timedelta (from MySQL TIME column) to time object."""
    if isinstance(td, time):
        return td
    return (datetime.min.replace(tzinfo=timezone.utc) + td).time()


async def availability_service(organization_id: int, professional_id: int, procedure_id: int, date: date) -> list[datetime]:
    # Get the organization's opening and closing times
    organization = await search_organization_by_id(organization_id)

    settings = await get_organization_settings(organization_id)

    if settings is None:
        settings = {"operating_weekdays": [1, 2, 3, 4, 5, 6, 7]}

    # Get the selected date's weekday and convert it to the Booking Engine date convention
    # e.g Sunday: weekday() = 6 → (6 + 2) % 7 = 8 % 7 = 1 (Booking Engine date)
    day = (date.weekday() + 2) % 7 or 7

    # Verify if the day chosen is in the organization operating_weekdays
    if day not in settings["operating_weekdays"]:
        raise ValueError("Organization doesn't operate on this day.")

    # Get the professionals buffer time and if he is_active
    professional = await search_professional_by_id(professional_id)
    # Get the procedures duration minutes and if it is_active
    procedure = await search_procedure_by_id(procedure_id)

    # Check if the professional actually offers this procedure and if it is_active
    is_active = True
    professional_procedure = await search_professional_procedure_unique(organization_id, professional_id,
                                                                        procedure_id, is_active)
    if not professional_procedure:
        raise ValueError("Professional doesn't offer this procedure.")

    # Working hours use Monday=1 through Sunday=7.
    day = date.weekday() + 1
    # Check if the professional is working in the day to be scheduled
    pro_working_hours = await list_active_working_hours_by_professional(professional_id)
    is_working = False
    for working_hours in pro_working_hours:
        if working_hours["weekday"] == day:
            is_working = True
            start_time = _timedelta_to_time(working_hours["start_time"])
            end_time = _timedelta_to_time(working_hours["end_time"])
            break

    # If the professional doesn't work in the selected date, raise ValueError
    if not is_working:
        raise ValueError("The professional doesn't work in the selected date.")

    # Else, combine the start_time and end_time to the selected date for a full DD/MM/YY - HH/MM/SS
    dt_start = datetime.combine(date, start_time)
    dt_end = datetime.combine(date, end_time)

    # Get the organizations min and max work time
    org_min_work = _timedelta_to_time(organization["min_work_time"])
    org_max_work = _timedelta_to_time(organization["max_work_time"])
    
    organization_start = datetime.combine(date, org_min_work)
    organization_end = datetime.combine(date, org_max_work)

    # Check for a invalid organization time range
    if organization_start >= organization_end:
        raise ValueError("Invalid organization work time range.")

    # Adjust the start and end dates to fit the organization work time
    if dt_start < organization_start:
        dt_start = max(dt_start, organization_start)
    if dt_end > organization_end:
        dt_end = min(dt_end, organization_end)

    # Free intervals for booking (currently the time between the start and end time of the working hour for the day)
    free_intervals = [
        (dt_start, dt_end)
    ]

    # Check if the professional has a blackout planned for that day
    pro_blackouts = await list_blackouts_by_professional(professional_id)

    blackout_intervals = free_intervals.copy()

    for blackout in pro_blackouts:
        # Verify if the blackout was accepted
        if blackout["status"] != "ACCEPTED":
            continue

        # Check if this blackout overlaps the working period
        if blackout["start_at"] < dt_end and blackout["end_at"] > dt_start:
            blackout_start = blackout["start_at"]
            blackout_end = blackout["end_at"]

            # Create a new list to keep all remaining free intervals (specially necessary if a blackout is registered)
            new_intervals = []
    
            # Check how the blackout affects each free interval
            for interval_start, interval_end in blackout_intervals:
                # If there isn't any overlap, keep the entire intevral (add it to the list)
                if blackout_end <= interval_start or blackout_start >= interval_end:
                    new_intervals.append((interval_start, interval_end))
                    continue

                # If there is a free space before the blackout, keep it by adding it to the list
                if interval_start < blackout_start:
                    new_intervals.append((interval_start, blackout_start))
                # If there is a free space after the blackout, add it to the list
                if blackout_end < interval_end:
                    new_intervals.append((blackout_end, interval_end))

            # Use this results for the next blackout (interation)
            blackout_intervals = new_intervals

    # Update the available intervals
    free_intervals = blackout_intervals

    app_intervals = free_intervals.copy()
    # Get all registered appointments for the selected date
    day_start = datetime.combine(date, time.min)
    day_end = day_start + timedelta(days=1)

    registered_appointments = await list_appointments_by_time_frame(organization_id,
                                                                  professional_id,
                                                                  start_at=day_start,
                                                                  end_at=day_end)
    for appointment in registered_appointments:
        # Get the appointments start time and their end time + buffer (for setting the procedure up)
        blocked_start = appointment["start_at"]
        blocked_end = (
            appointment["end_at"]
            + timedelta(minutes=professional["buffer_time_minutes"])
        )

        # Create a list to store the new intervals
        new_intervals = []

        for interval_start, interval_end in app_intervals:
            # If there isn't any overlays between the full procedure time
            # and the available time slot for it, keep the interval
            if blocked_end <= interval_start or blocked_start >= interval_end:
                new_intervals.append((interval_start, interval_end))
                continue

            # If there is a free space before the appointment, add the interval
            if interval_start < blocked_start:
                new_intervals.append((interval_start, blocked_start))
            # If there is a free space after the end of the appointment + buffer, add it
            if blocked_end < interval_end:
                new_intervals.append((blocked_end, interval_end))
        # Update the intervals with the new info for the next appointment booking
        app_intervals = new_intervals
    # Update overall
    free_intervals = app_intervals

    # Get the full duration the procedure + buffer is going to take
    slot_duration = timedelta(
        minutes=procedure["duration_minutes"]
        + professional["buffer_time_minutes"]
    )
    # Intervals between possible start times must be 15 minutes
    slot_interval = timedelta(minutes=15)

    available_slots = []

    for interval_start, interval_end in free_intervals:
        current_start = interval_start

        while current_start + slot_duration <= interval_end:
            # Add it to the available slot
            available_slots.append(current_start)
            # Get next possible slot
            current_start += slot_interval

    # Return the available slots the new appointment can be chosen
    return available_slots