"""
Root-level report generation endpoints for global data access.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.v1.middleware.rate_limiter import limiter
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.cache_service import set_cached
from app.api.v1.services.report_generator import (
    generate_csv_report,
    generate_pdf_report,
)
from app.api.v1.services.report_service import (
    generate_appointments_report,
    generate_customers_report,
    generate_revenue_report,
)
from app.api.v1.services.user_service import is_root

router = APIRouter(prefix="/v1/root")


@router.get("/reports/appointments/global", status_code=200)
@limiter.limit("2/minute")
async def global_appointments_report(
    request: Request,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    professional_id: int | None = None,
    customer_id: int | None = None,
    format: str = "pdf",
    user_id: int = Depends(verify_user_token)
):
    # Check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")
    
    # If the format is None, default to pdf
    if format not in ["pdf", "csv"]:
        format = "pdf"

    report_data = await generate_appointments_report(
        org_id=None,
        start_date=start_date,
        end_date=end_date,
        professional_id=professional_id,
        customer_id=customer_id
    )

    # Manual caching
    cache_key = f"cache:global_report_appointments:{start_date}:{end_date}:{professional_id}:{customer_id}"
    set_cached(cache_key, report_data, ttl=300)
    
    if format == "pdf":
        pdf_buffer = generate_pdf_report(report_data)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=appointments_report.pdf"}
        )
    else:
        csv_buffer = generate_csv_report(report_data)
        return StreamingResponse(
            csv_buffer,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=appointments_report.csv"}
        )


@router.get("/reports/revenue/global", status_code=200)
@limiter.limit("2/minute")
async def global_revenue_report(
    request: Request,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    professional_id: int | None = None,
    group_by: str = "month",
    format: str = "pdf",
    user_id: int = Depends(verify_user_token)
):
    # Check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")
    
    # If the format is None, default to pdf
    if format not in ["pdf", "csv"]:
        format = "pdf"
    
    report_data = await generate_revenue_report(
        org_id=None,
        start_date=start_date,
        end_date=end_date,
        professional_id=professional_id,
        group_by=group_by
    )

    # Manual caching
    cache_key = f"cache:global_report_revenue:{start_date}:{end_date}:{professional_id}:{group_by}"
    set_cached(cache_key, report_data, ttl=300)
    
    if format == "pdf":
        pdf_buffer = generate_pdf_report(report_data)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=revenue_report.pdf"}
        )
    else:
        csv_buffer = generate_csv_report(report_data)
        return StreamingResponse(
            csv_buffer,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=revenue_report.csv"}
        )


@router.get("/reports/customers/global", status_code=200)
@limiter.limit("2/minute")
async def global_customers_report(
    request: Request,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    professional_id: int | None = None,
    format: str = "pdf",
    user_id: int = Depends(verify_user_token)
):
    # Check if the current user is root; If not, return 403
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")
    
    # If the format is None, default to pdf
    if format not in ["pdf", "csv"]:
        format = "pdf"
    
    report_data = await generate_customers_report(
        org_id=None,
        start_date=start_date,
        end_date=end_date,
        professional_id=professional_id
    )

    # Manual caching
    cache_key = f"cache:global_report_customers:{start_date}:{end_date}:{professional_id}"
    set_cached(cache_key, report_data, ttl=300)
    
    if format == "pdf":
        pdf_buffer = generate_pdf_report(report_data)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=customers_report.pdf"}
        )
    else:
        csv_buffer = generate_csv_report(report_data)
        return StreamingResponse(
            csv_buffer,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=customers_report.csv"}
        )