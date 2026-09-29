"""
Redis operations for checking and storing idempotent request responses.
"""

import json

from redis import Redis


async def check_idempotent_request(
    redis_client: Redis,
    org_id: int, 
    idempotency_key: str
) -> tuple[bool, dict | None]:
    """
    Checks whether an organization-scoped idempotency key has a cached response.

    Args:
        redis_client: The Redis client used to retrieve the cached value
        org_id: The organization ID that scopes the idempotency key
        idempotency_key: The request's idempotency key

    Returns:
        tuple[bool, dict | None]: Whether a cached response exists and its decoded payload, if present

    Raises:
        json.JSONDecodeError: If the cached value is not valid JSON
    """
    redis_key = f"idempotency:{org_id}:{idempotency_key}"
    cached = redis_client.get(redis_key)
    
    if cached:
        return True, json.loads(cached)
    
    return False, None


async def store_response(
    redis_client: Redis,
    org_id: int,
    idempotency_key: str,
    status_code: int,
    response_body: dict
) -> None:
    """
    Stores an organization-scoped response payload in Redis for five minutes.

    Args:
        redis_client: The Redis client used to store the response
        org_id: The organization ID that scopes the idempotency key
        idempotency_key: The request's idempotency key
        status_code: The HTTP status code to cache
        response_body: The response body to cache

    Returns:
        None: This function stores the serialized response without returning a value
    """
    redis_key = f"idempotency:{org_id}:{idempotency_key}"
    
    payload = {
        "status_code": status_code,
        "body": response_body
    }
    
    # Serialize to JSON and store for 5 mins
    redis_client.set(
        redis_key,
        json.dumps(payload),
        ex=300
    )