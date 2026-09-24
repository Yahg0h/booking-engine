"""
All services related to audit logs used across all Booking Engine routes.
"""

import json

from sqlalchemy import text

from app.database import engine


async def log_action(
    organization_id: int | None,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    old_values: dict | None,
    new_values: dict | None,
    metadata: dict | None,
    ip_address: str | None
) -> int:
    """
    Records an audit log entry for a system action.

    Args:
        organization_id: The organization context for the audit log
        actor_user_id: The user who triggered the action
        action: The action type being recorded
        entity_type: The resource type affected by the action
        entity_id: The ID of the affected entity
        old_values: The previous values before the change
        new_values: The values after the change
        metadata: Additional structured context for the log
        ip_address: The client IP address associated with the action

    Returns:
        int: The ID of the newly created audit log entry
    """
    # If there is values, convert them from dict to JSON
    old_values_json = json.dumps(old_values, default=str) if old_values else None
    new_values_json = json.dumps(new_values, default=str) if new_values else None
    metadata_json = json.dumps(metadata, default=str) if metadata else None

    # Connect to database
    async with engine.begin() as conn:
        insert_query = """
        INSERT INTO audit_logs (organization_id, actor_user_id, action, entity_type, entity_id, old_values, new_values, metadata, ip_address)
        VALUES (:organization_id, :actor_user_id, :action, :entity_type, :entity_id, :old_values, :new_values, :metadata, :ip_address)
        """
        await conn.execute(text(insert_query), {"organization_id": organization_id, "actor_user_id": actor_user_id, "action": action,
                                                "entity_type": entity_type, "entity_id": entity_id, "old_values": old_values_json,
                                                "new_values": new_values_json, "metadata": metadata_json, "ip_address": ip_address})

        # Get the id of the recently created log
        search_query = """
        SELECT id FROM audit_logs
        WHERE organization_id = :organization_id AND actor_user_id = :actor_user_id AND entity_type = :entity_type AND old_values = :old_values AND
        new_values = :new_values AND metadata = :metadata AND ip_address = :ip_address
        ORDER BY id DESC LIMIT 1
        """
        query = await conn.execute(text(search_query), {"organization_id": organization_id, "actor_user_id": actor_user_id, "action": action,
                                                "entity_type": entity_type, "entity_id": entity_id, "old_values": old_values_json,
                                                "new_values": new_values_json, "metadata": metadata_json, "ip_address": ip_address})
        recent_log_id = query.scalar()

        return recent_log_id

async def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    actor_user_id: int | None = None,
    entity_type: str | None = None,
    action: str | None = None
) -> list[dict]:
    """
    Fetches audit logs using optional filters.

    Args:
        limit: Maximum number of logs to return
        offset: Pagination offset for the result set
        actor_user_id: Filter by user ID (optional)
        entity_type: Filter by resource type (optional)
        action: Filter by action type (optional)

    Returns:
        list[dict]: A list of audit log dictionaries matching the filters
    """
    # Create a dynamic query that changes based on the filters selected
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = {}

    if actor_user_id is not None:
        query += " AND actor_user_id = :actor_user_id"
        params["actor_user_id"] = actor_user_id

    if entity_type is not None:
        query += " AND entity_type = :entity_type"
        params["entity_type"] = entity_type

    if action is not None:
        query += " AND action = :action"
        params["action"] = action

    # Connect to database
    async with engine.connect() as conn:
        # Get log info for each audit log found (for those that fall under the selected filters)
        paginated_query = query + " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        result = await conn.execute(text(paginated_query), params)
        logs = result.mappings().all()

        # Convert each log to a list and then add each log info to a list
        log_list = [dict(log_row) for log_row in logs]

    # Return the list with all info (log_list)
    return log_list

# Utility functions related to audit_service
def get_ip_from_request(request) -> str | None:
    """
    Extracts the client IP address from a FastAPI request.

    Args:
        request: The FastAPI request object

    Returns:
        str | None: The client IP address, or None if it cannot be determined
    """
    # Try fetching the IP address from the client connection
    if request.client and request.client.host:
        return request.client.host

    # If IP not available/found, try looking for it in the proxies header
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # The first IP in the list is the client original only, no proxies
        return forwarded_for.split(",")[0].strip()

    # If nothing works and IP can't be found, return None
    return None

def sanitize_audit_values(data: dict | None) -> dict | None:
    """
    Removes sensitive values from audit payloads before logging.

    Args:
        data: The raw dictionary payload to sanitize

    Returns:
        dict | None: A sanitized dictionary without password hashes, or None if no data is provided
    """
    if not data:
        return None

    sanitized = data.copy()
    sanitized.pop("password_hash", None)
    return sanitized
