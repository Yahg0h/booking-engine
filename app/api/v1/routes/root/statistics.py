"""
Routes for viewing statistics by root-level accounts.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.middleware.rate_limiter import limiter
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.cache_service import set_cached
from app.api.v1.services.organization_service import search_organization_by_id
from app.api.v1.services.statistics_service import (
    get_appointments_statistics,
    get_appointments_statistics_global,
    get_customers_statistics,
    get_customers_statistics_global,
    get_revenue_statistics,
    get_revenue_statistics_global,
)
from app.api.v1.services.user_service import is_root

router = APIRouter(prefix="/v1/root")

@router.get("/statistics/appointments/global", status_code=200)
@limiter.limit("5/minute")
async def all_appointment_statistics(request: Request, start_date: datetime | None = None, end_date: datetime | None = None, user_id: int = Depends(verify_user_token)):
    """
    Retrieves and caches appointment statistics across all organizations.

    Args:
        request: The FastAPI request used by the rate limiter
        start_date: The beginning of the reporting period (optional)
        end_date: The end of the reporting period (optional)
        user_id: The ID of the authenticated user

    Returns:
        dict: Global appointment totals, cancellation and no-show counts and rates, and the reporting period

    Raises:
        HTTPException: If the authenticated user is not a root administrator

    Notes:
        A serialized copy of the result is cached for 5 minutes
    """
    # Check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")
    
    # Get global appointments statistics (all organizations)
    all_appts_stats = await get_appointments_statistics_global(start_date, end_date)

    # Manual caching (converts datas to string)
    result_to_cache = {
        **all_appts_stats,
        "period": {
            "start_date": all_appts_stats["period"]["start_date"].isoformat(),
            "end_date": all_appts_stats["period"]["end_date"].isoformat()
        }
    }

    cache_key = f"cache:appointments_global:{start_date or 'default'}:{end_date or 'default'}"
    set_cached(cache_key, result_to_cache, ttl=300)

    return all_appts_stats

@router.get("/statistics/revenue/global", status_code=200)
@limiter.limit("5/minute")
async def all_revenue_statistics(request: Request, start_date: datetime | None = None, end_date: datetime | None = None, group_by: str = 'week', user_id: int = Depends(verify_user_token)):
    """
    Retrieves and caches revenue statistics across all organizations.

    Args:
        request: The FastAPI request used by the rate limiter
        start_date: The beginning of the reporting period (optional)
        end_date: The end of the reporting period (optional)
        group_by: The revenue grouping interval ('week', 'month' or 'year')
        user_id: The ID of the authenticated user

    Returns:
        dict: Global estimated and concrete revenue grouped by date, with the reporting period

    Raises:
        HTTPException: If the authenticated user is not a root administrator

    Notes:
        A serialized copy of the result is cached for 10 minutes
    """
    # Check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Get the global revenue statistics (all organizations)
    all_rev_stats = await get_revenue_statistics_global(start_date, end_date, group_by)

    # Manual caching (converts datas to string)
    result_to_cache = {
        **all_rev_stats,
        "period": {
            "start_date": all_rev_stats["period"]["start_date"].isoformat(),
            "end_date": all_rev_stats["period"]["end_date"].isoformat()
        }
    }

    cache_key = f"cache:revenue_global:{start_date or 'default'}:{end_date or 'default'}"
    set_cached(cache_key, result_to_cache, ttl=600)

    return all_rev_stats

@router.get("/statistics/customers/global", status_code=200)
@limiter.limit("5/minute")
async def all_customer_statistics(request: Request, start_date: datetime | None = None, end_date: datetime | None = None, user_id: int = Depends(verify_user_token)):
    """
    Retrieves and caches customer statistics across all organizations.

    Args:
        request: The FastAPI request used by the rate limiter
        start_date: The beginning of the reporting period (optional)
        end_date: The end of the reporting period (optional)
        user_id: The ID of the authenticated user

    Returns:
        dict: Global customer counts, engagement rate, per-professional counts, and reporting period

    Raises:
        HTTPException: If the authenticated user is not a root administrator

    Notes:
        A serialized copy of the result is cached for 15 minutes
    """
    # Check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Get the global customer statistics (all organizations)
    all_customers_stats = await get_customers_statistics_global(start_date, end_date)

    # Manual caching (converts datas to string)
    result_to_cache = {
        **all_customers_stats,
        "period": {
            "start_date": all_customers_stats["period"]["start_date"].isoformat(),
            "end_date": all_customers_stats["period"]["end_date"].isoformat()
        }
    }

    cache_key = f"cache:customers_global:{start_date or 'default'}:{end_date or 'default'}"
    set_cached(cache_key, result_to_cache, ttl=900)

    return all_customers_stats

@router.get("/statistics/appointments/{organization_id}", status_code=200)
@limiter.limit("5/minute")
async def appointment_statistics(request: Request, organization_id: int, start_date: datetime | None = None, end_date: datetime | None = None, user_id: int = Depends(verify_user_token)):
    """
    Retrieves and caches appointment statistics for a specific organization.

    Args:
        request: The FastAPI request used by the rate limiter
        organization_id: The organization ID to report on
        start_date: The beginning of the reporting period (optional)
        end_date: The end of the reporting period (optional)
        user_id: The ID of the authenticated user

    Returns:
        dict: Appointment totals, cancellation and no-show counts and rates, and the reporting period

    Raises:
        HTTPException: If the organization does not exist or the user is not a root administrator

    Notes:
        A serialized copy of the result is cached for 5 minutes
    """
    # Check if the organization exists
    is_real = await search_organization_by_id(organization_id)

    if not is_real:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # If it does, check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Get appointments statistics for the organization
    appts_stats = await get_appointments_statistics(organization_id, start_date, end_date)

    # Manual caching (converts datas to string)
    cache_key = f"cache:appointment_statistics:{organization_id}:{start_date}:{end_date}"
    result_to_cache = {
        **appts_stats,
        "period": {
            "start_date": appts_stats["period"]["start_date"].isoformat(),
            "end_date": appts_stats["period"]["end_date"].isoformat()
        }
    }
    set_cached(cache_key, result_to_cache, ttl=300)

    return appts_stats

@router.get("/statistics/revenue/{organization_id}", status_code=200)
@limiter.limit("5/minute")
async def revenue_statistics(request: Request, organization_id: int, start_date: datetime | None = None, end_date: datetime | None = None, group_by: str = 'week', user_id: int = Depends(verify_user_token)):
    """
    Retrieves and caches revenue statistics for a specific organization.

    Args:
        request: The FastAPI request used by the rate limiter
        organization_id: The organization ID to report on
        start_date: The beginning of the reporting period (optional)
        end_date: The end of the reporting period (optional)
        group_by: The revenue grouping interval ('week', 'month' or 'year')
        user_id: The ID of the authenticated user

    Returns:
        dict: Estimated and concrete revenue grouped by date, with the reporting period

    Raises:
        HTTPException: If the organization does not exist or the user is not a root administrator

    Notes:
        A serialized copy of the result is cached for 10 minutes
    """
    # Check if the organization exists
    is_real = await search_organization_by_id(organization_id)

    if not is_real:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # If it does, check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Get the organization's revenue statistics
    rev_stats = await get_revenue_statistics(organization_id, start_date, end_date, group_by)

    # Manual caching (converts datas to string)
    cache_key = f"cache:revenue_statistics:{organization_id}:{start_date}:{end_date}"
    result_to_cache = {
        **rev_stats,
        "period": {
            "start_date": rev_stats["period"]["start_date"].isoformat(),
            "end_date": rev_stats["period"]["end_date"].isoformat()
        }
    }
    set_cached(cache_key, result_to_cache, ttl=600)

    return rev_stats

@router.get("/statistics/customers/{organization_id}", status_code=200)
@limiter.limit("5/minute")
async def customer_statistics(request: Request, organization_id: int, start_date: datetime | None = None, end_date: datetime | None = None, user_id: int = Depends(verify_user_token)):
    """
    Retrieves and caches customer statistics for a specific organization.

    Args:
        request: The FastAPI request used by the rate limiter
        organization_id: The organization ID to report on
        start_date: The beginning of the reporting period (optional)
        end_date: The end of the reporting period (optional)
        user_id: The ID of the authenticated user

    Returns:
        dict: Customer counts, engagement rate, per-professional counts, and reporting period

    Raises:
        HTTPException: If the organization does not exist or the user is not a root administrator

    Notes:
        A serialized copy of the result is cached for 15 minutes
    """
    # Check if the organization exists
    is_real = await search_organization_by_id(organization_id)

    if not is_real:
        raise HTTPException(status_code=404, detail="Organization not found or doesn't exist.")

    # If it does, check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")

    # Get the organization's customer statistics
    customers_stats = await get_customers_statistics(organization_id, start_date, end_date)

    # Manual caching (converts datas to string)
    cache_key = f"cache:customer_statistics:{organization_id}:{start_date}:{end_date}"
    result_to_cache = {
        **customers_stats,
        "period": {
            "start_date": customers_stats["period"]["start_date"].isoformat(),
            "end_date": customers_stats["period"]["end_date"].isoformat()
        }
    }
    set_cached(cache_key, result_to_cache, ttl=900)

    return customers_stats