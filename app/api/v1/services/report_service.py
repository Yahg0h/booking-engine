"""
Services for generating report data with metadata and summaries.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import create_engine, text

from app.database import DATABASE_URL

engine_sync = create_engine(
    DATABASE_URL.replace("+aiomysql", "+pymysql"),
    echo=False
)


def _read_sql_sync(query: str, params: dict) -> pd.DataFrame:
    """Executes parameterized SQL and returns DataFrame."""
    with engine_sync.begin() as conn:
        result = conn.execute(text(query), params)
        return pd.DataFrame(result.mappings())


async def generate_appointments_report(
    org_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    professional_id: int | None = None,
    customer_id: int | None = None
) -> dict:
    """
    Generates appointment report data with metadata and summary.

    Args:
        org_id: Organization ID (None for global)
        start_date: Report period start (default: 30 days ago)
        end_date: Report period end (default: now)
        professional_id: Filter by professional (optional)
        customer_id: Filter by customer (optional)

    Returns:
        dict with metadata, summary, and DataFrame
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Build filters dynamically
    filters = []
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }

    if org_id is not None:
        filters.append("AND a.organization_id = :org_id")
        params["org_id"] = org_id

    if professional_id is not None:
        filters.append("AND a.professional_id = :professional_id")
        params["professional_id"] = professional_id

    if customer_id is not None:
        filters.append("AND a.customer_id = :customer_id")
        params["customer_id"] = customer_id

    filters_str = " ".join(filters)

    query = f"""
        SELECT
            a.id AS appointment_id,
            a.start_at AS appointment_start,
            a.status AS appointment_status,
            p.name AS professional_name,
            c.email AS customer_email,
            pr.name AS procedure_name,
            pr.price AS procedure_price
        FROM appointments a
        JOIN professionals p ON a.professional_id = p.id
        JOIN customers c ON a.customer_id = c.id
        JOIN procedures pr ON a.procedure_id = pr.id
        WHERE a.created_at BETWEEN :start_date AND :end_date
            {filters_str}
        ORDER BY a.start_at DESC
    """

    df = await asyncio.to_thread(_read_sql_sync, query, params)

    # Calculate summary
    if df.empty:
        summary = {
            "total_appointments": 0,
            "completed": 0,
            "cancelled": 0,
            "no_show": 0,
            "total_revenue": 0.0
        }
    else:
        summary = {
            "total_appointments": len(df),
            "completed": len(df[df['appointment_status'] == 'COMPLETED']),
            "cancelled": len(df[df['appointment_status'] == 'CANCELLED']),
            "no_show": len(df[df['appointment_status'] == 'NO_SHOW']),
            "total_revenue": float(df['procedure_price'].sum())
        }

    return {
        "metadata": {
            "report_title": "Appointments Report",
            "generated_at": datetime.now(timezone.utc),
            "organization_id": org_id,
            "organization_name": None,  # Set in routes if needed
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "filters_applied": {
                "professional_id": professional_id,
                "customer_id": customer_id
            }
        },
        "summary": summary,
        "data": df
    }


async def generate_revenue_report(
    org_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    professional_id: int | None = None,
    group_by: str = "month"
) -> dict:
    """
    Generates revenue report data with metadata and summary.

    Args:
        org_id: Organization ID (None for global)
        start_date: Report period start (default: 30 days ago)
        end_date: Report period end (default: now)
        professional_id: Filter by professional (optional)
        group_by: Grouping interval ('week', 'month', 'year')

    Returns:
        dict with metadata, summary, and DataFrame
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        # Calculates based on group_by
        if group_by == "week":
            start_date = end_date - timedelta(days=7)
        elif group_by == "month":
            start_date = end_date - timedelta(days=30)
        elif group_by == "year":
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)

    filters = []
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }

    if org_id is not None:
        filters.append("AND a.organization_id = :org_id")
        params["org_id"] = org_id

    if professional_id is not None:
        filters.append("AND a.professional_id = :professional_id")
        params["professional_id"] = professional_id

    filters_str = " ".join(filters)

    query = f"""
        SELECT
            a.id AS appointment_id,
            a.start_at AS appointment_start,
            a.status AS appointment_status,
            p.name AS professional_name,
            pr.name AS procedure_name,
            pr.price AS procedure_price,
            CASE WHEN a.start_at < NOW() THEN 'Concrete' ELSE 'Estimated' END AS revenue_type
        FROM appointments a
        JOIN professionals p ON a.professional_id = p.id
        JOIN procedures pr ON a.procedure_id = pr.id
        WHERE a.start_at BETWEEN :start_date AND :end_date
            {filters_str}
        ORDER BY a.start_at DESC
    """

    df = await asyncio.to_thread(_read_sql_sync, query, params)

    # Calculate summary
    if df.empty:
        summary = {
            "total_estimated_revenue": 0.0,
            "total_concrete_revenue": 0.0,
            "appointment_count": 0
        }
    else:
        summary = {
            "total_estimated_revenue": float(df['procedure_price'].sum()),
            "total_concrete_revenue": float(df[df['revenue_type'] == 'Concrete']['procedure_price'].sum()),
            "appointment_count": len(df)
        }

    return {
        "metadata": {
            "report_title": "Revenue Report",
            "generated_at": datetime.now(timezone.utc),
            "organization_id": org_id,
            "organization_name": None,
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "filters_applied": {
                "professional_id": professional_id,
                "group_by": group_by
            }
        },
        "summary": summary,
        "data": df
    }


async def generate_customers_report(
    org_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    professional_id: int | None = None
) -> dict:
    """
    Generates customer engagement report data with metadata and summary.

    Args:
        org_id: Organization ID (None for global)
        start_date: Report period start (default: 30 days ago)
        end_date: Report period end (default: now)
        professional_id: Filter by professional (optional)

    Returns:
        dict with metadata, summary, and DataFrame
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    filters = []
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }

    if org_id is not None:
        filters.append("AND a.organization_id = :org_id")
        params["org_id"] = org_id

    if professional_id is not None:
        filters.append("AND a.professional_id = :professional_id")
        params["professional_id"] = professional_id

    filters_str = " ".join(filters)

    query = f"""
        SELECT
            c.id AS customer_id,
            c.email AS customer_email,
            c.phone AS customer_phone,
            c.is_active AS customer_active,
            c.last_appointment_at AS last_appointment,
            COUNT(DISTINCT a.id) AS total_appointments,
            COUNT(DISTINCT a.professional_id) AS professionals_visited
        FROM customers c
        LEFT JOIN appointments a ON a.customer_id = c.id
            AND a.start_at BETWEEN :start_date AND :end_date
            {filters_str}
        {'WHERE c.organization_id = :org_id' if org_id is not None else ''}
        GROUP BY c.id, c.email, c.phone, c.is_active, c.last_appointment_at
        ORDER BY total_appointments DESC
    """

    df = await asyncio.to_thread(_read_sql_sync, query, params)

    # Calculate summary
    if df.empty:
        summary = {
            "total_customers": 0,
            "active_customers": 0,
            "inactive_customers": 0,
            "avg_appointments_per_customer": 0.0
        }
    else:
        summary = {
            "total_customers": len(df),
            "active_customers": len(df[df['customer_active'] == True]),
            "inactive_customers": len(df[df['customer_active'] == False]),
            "avg_appointments_per_customer": round(df['total_appointments'].mean(), 2)
        }

    return {
        "metadata": {
            "report_title": "Customers Report",
            "generated_at": datetime.now(timezone.utc),
            "organization_id": org_id,
            "organization_name": None,
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "filters_applied": {
                "professional_id": professional_id
            }
        },
        "summary": summary,
        "data": df
    }