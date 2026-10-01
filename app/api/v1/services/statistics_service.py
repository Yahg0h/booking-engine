"""
Services for calculating organization-level and global business statistics.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import create_engine, text

from app.database import DATABASE_URL

# Synchronous engine for pandas to use instead of the default async
engine_sync = create_engine(
    DATABASE_URL.replace("+aiomysql", "+pymysql"),
    echo=False
)


def _read_sql_sync(query: str, params: dict) -> pd.DataFrame:
    """
    Executes a parameterized SQL query and returns its rows as a DataFrame.

    Args:
        query: The SQL statement to execute
        params: The values bound to the SQL statement parameters

    Returns:
        pd.DataFrame: The query result rows
    """
    with engine_sync.begin() as conn:
        result = conn.execute(text(query), params)
        return pd.DataFrame(result.mappings())
    

async def get_appointments_statistics(
    org_id: int | None,
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> dict:
    """
    Calculates appointment counts and outcome rates for an organization or globally.

    Args:
        org_id: The organization ID to report on, or None to include all organizations
        start_date: The inclusive start of the creation-date period (optional)
        end_date: The inclusive end of the creation-date period (optional)

    Returns:
        dict: Appointment totals, cancellation and no-show counts and rates, and the effective period
    """
    # Sets the default period (last 30 days) if dates are not provided
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Adds the org_id condition dynamically.
    org_filter = "AND organization_id = :org_id" if org_id is not None else ""
    
    query = f"""
        SELECT 
            COUNT(*) AS total,
            COUNT(CASE WHEN status = 'CANCELLED' THEN 1 END) AS cancelled,
            COUNT(CASE WHEN status = 'NO_SHOW' THEN 1 END) AS no_show
        FROM appointments
        WHERE created_at BETWEEN :start_date AND :end_date
            {org_filter}
    """

    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
    if org_id is not None:
        params["org_id"] = org_id

    # Synchronous reading on a separate thread so as not to block the main async event loop
    df = await asyncio.to_thread(_read_sql_sync, query, params)

    # Returns zeroed-out statistics if there are no records for the period
    if df.empty or df["total"].iloc[0] == 0:
        return {
            "total": 0,
            "cancelled": 0,
            "no_show": 0,
            "tax_cancelled": 0.0,
            "tax_no_show": 0.0,
            "period": {"start_date": start_date, "end_date": end_date}
        }

    # Filters and calculates quantities and percentage rates (tax) of cancellations and no-shows
    total = int(df["total"].iloc[0])
    cancelled = int(df["cancelled"].iloc[0])
    no_show = int(df["no_show"].iloc[0])

    # Return data
    return {
        "total": total,
        "cancelled": cancelled,
        "no_show": no_show,
        "tax_cancelled": round((cancelled / total) * 100, 2),
        "tax_no_show": round((no_show / total) * 100, 2),
        "period": {"start_date": start_date, "end_date": end_date}
    }


async def get_revenue_statistics(
    org_id: int | None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    group_by: str = "week"
) -> dict:
    """
    Calculates estimated and realized appointment revenue for the selected organization scope.

    Args:
        org_id: The organization ID used to scope the query; the global wrapper passes None
        start_date: The beginning of the reporting period (optional)
        end_date: The end of the reporting period (optional)
        group_by: The revenue grouping interval, such as 'week', 'month', or 'year'

    Returns:
        dict: Estimated and concrete revenue grouped by date, with the effective period and grouping
    """
    if end_date is None:
        # Makes end_date today
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

    # Converts datetime to strings in ISO format
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()
    
    org_filter = "AND a.organization_id = :org_id" if org_id is not None else ""

    query = f"""
        SELECT 
            a.id,
            a.start_at,
            a.status,
            p.price
        FROM appointments a
        JOIN procedures p ON a.procedure_id = p.id
        WHERE a.start_at BETWEEN :start_date AND :end_date
            {org_filter}
    """

    params = {
        "start_date": start_date_str,
        "end_date": end_date_str
    }
    if org_id is not None:
        params["org_id"] = org_id

    # Executes the query off-thread to not block main async event loop
    df = await asyncio.to_thread(_read_sql_sync, query, params)

    # Returns zeroed-out statistics if there are no records for the period
    if df.empty:
        return {
            "estimated": {},
            "concrete": {},
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "group_by": group_by
            }
        }

    # Converts the column to the pandas datetime type
    df['start_at'] = pd.to_datetime(df['start_at'], utc=True)

    # Maps the parameter groupings to the corresponding Pandas frequency
    freq_map = {
        "week": "W",
        "month": "MS",
        "year": "YS"
    }
    freq = freq_map.get(group_by, "W")

    # Gets current datetime without tzinfo for direct date comparison in the DataFrame
    now = datetime.now(timezone.utc)

    # Considers only appointments that have already taken place (start_at in the past) as 'concrete' revenue
    df_concrete = df[df['start_at'] < now]

    # Groups and sums estimated revenue (all within the period) and actual revenue (past only) by time frequency
    estimated_series = df.groupby(pd.Grouper(key='start_at', freq=freq))['price'].sum()
    concrete_series = df_concrete.groupby(pd.Grouper(key='start_at', freq=freq))['price'].sum()

    # Formats the grouped results into dicts with keys in 'YYYY-MM-DD'
    estimated_dict = {
        k.strftime('%Y-%m-%d'): float(v) 
        for k, v in estimated_series.to_dict().items() if v > 0
    }
    concrete_dict = {
        k.strftime('%Y-%m-%d'): float(v) 
        for k, v in concrete_series.to_dict().items() if v > 0
    }

    # Return data
    return {
        "estimated": estimated_dict,
        "concrete": concrete_dict,
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "group_by": group_by
        }
    }


async def get_customers_statistics(
    org_id: int | None,
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> dict:
    """
    Calculates customer engagement and per-professional statistics for the selected organization scope.

    Args:
        org_id: The organization ID used to scope the queries; the global wrapper passes None
        start_date: The beginning of the customer activity period (optional)
        end_date: The end of the customer activity period (optional)

    Returns:
        dict: Unique customers per professional, engaged and inactive counts, engagement rate, and period
    """
    # Sets the default period (last 30 days) if dates are not provided
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Converts datetime to strings in ISO format
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()

    org_filter = "WHERE organization_id = :org_id" if org_id is not None else ""

    if org_id is not None:
        query_prof_customers = """
            SELECT 
                p.id AS professional_id,
                p.name AS professional_name,
                COUNT(DISTINCT a.customer_id) AS unique_customers
            FROM professionals p
            LEFT JOIN appointments a ON a.professional_id = p.id
                AND a.organization_id = :org_id
                AND a.start_at BETWEEN :start_date AND :end_date
            WHERE p.organization_id = :org_id
            GROUP BY p.id, p.name
        """
    else:
        query_prof_customers = """
            SELECT 
                p.id AS professional_id,
                p.name AS professional_name,
                COUNT(DISTINCT a.customer_id) AS unique_customers
            FROM professionals p
            LEFT JOIN appointments a ON a.professional_id = p.id
                AND a.start_at BETWEEN :start_date AND :end_date
            GROUP BY p.id, p.name
        """

    query_customer_counts = f"""
        SELECT 
            COUNT(CASE WHEN last_appointment_at BETWEEN :start_date AND :end_date THEN 1 END) AS engaged_count,
            COUNT(CASE WHEN last_appointment_at IS NULL OR last_appointment_at < :start_date THEN 1 END) AS inactive_count,
            COUNT(*) AS total_count
        FROM customers
        {org_filter}
    """

    params = {
        "start_date": start_date_str,
        "end_date": end_date_str
    }
    if org_id is not None:
        params["org_id"] = org_id

    # Executes both queries in separate threads to not block async main event loop
    df_profs = await asyncio.to_thread(_read_sql_sync, query_prof_customers, params)
    df_status = await asyncio.to_thread(_read_sql_sync, query_customer_counts, params)

    # Converts the result of customers per professional into a structured dict
    unique_per_professional = {}
    if not df_profs.empty:
        unique_per_professional = {
            f"prof_{row['professional_id']}": int(row['unique_customers'])
            for row in df_profs.to_dict(orient="records")
        }

    # Extracts engagement totals and calculates the percentage rate of engaged customers
    if not df_status.empty and df_status["total_count"].iloc[0] > 0:
        engaged = int(df_status["engaged_count"].iloc[0])
        inactive = int(df_status["inactive_count"].iloc[0])
        total = int(df_status["total_count"].iloc[0])
        tax_engaged = round((engaged / total) * 100, 2) if total > 0 else 0.0
    else:
        engaged = 0
        inactive = 0
        tax_engaged = 0.0

    # Return data
    return {
        "unique_per_professional": unique_per_professional,
        "engaged": engaged,
        "inactive": inactive,
        "tax_engaged": tax_engaged,
        "period": {
            "start_date": start_date,
            "end_date": end_date
        }
    }


# ==== GLOBAL VARIANTS ====

async def get_appointments_statistics_global(
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> dict:
    """
    Calculates appointment counts and outcome rates across all organizations.

    Args:
        start_date: The inclusive start of the creation-date period (optional)
        end_date: The inclusive end of the creation-date period (optional)

    Returns:
        dict: Global appointment totals, cancellation and no-show counts and rates, and the effective period
    """
    return await get_appointments_statistics(org_id=None, start_date=start_date, end_date=end_date)

async def get_revenue_statistics_global(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    group_by: str = "week"
) -> dict:
    """
    Calculates estimated and realized appointment revenue across all organizations.

    Args:
        start_date: The beginning of the reporting period (optional)
        end_date: The end of the reporting period (optional)
        group_by: The revenue grouping interval, such as 'week', 'month', or 'year'

    Returns:
        dict: Global estimated and concrete revenue grouped by date, with the effective period and grouping
    """
    return await get_revenue_statistics(org_id=None, start_date=start_date, end_date=end_date, group_by=group_by)


async def get_customers_statistics_global(
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> dict:
    """
    Calculates customer engagement and per-professional statistics globally.

    Args:
        start_date: The beginning of the customer activity period (optional)
        end_date: The end of the customer activity period (optional)

    Returns:
        dict: Global unique customers per professional, engaged and inactive counts, engagement rate, and period
    """
    return await get_customers_statistics(org_id=None, start_date=start_date, end_date=end_date)