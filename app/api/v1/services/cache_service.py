"""
Redis-backed helpers used to coordinate booking locks and manage caching.
"""

import json
import logging

logger = logging.getLogger(__name__)

from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from typing import Any

import pandas as pd
import redis
from fastapi import Request

from app.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

# Default cache TTL from enviroment (in secs)
DEFAULT_CACHE_TTL = int(settings.CACHE_DEFAULT_TTL) if hasattr(settings, 'CACHE_DEFAULT_TTL') else 1800
HIGH_FREQUENCY_TTL = 5

def json_serializer(obj: Any) -> Any:
    """Helper serializer for `json.dumps` to handle datetime, decimal, and pandas objects."""
    # Handles native date/time objects and Pandas Timestamps.
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.isoformat()
    # Handles Decimal objects (financial/monetary values)
    if isinstance(obj, Decimal):
        return float(obj)
    # Handles Pandas DataFrames by converting them into a list of dictionaries.
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    # Handle Pandas Series by converting them to a list.
    if isinstance(obj, pd.Series):
        return obj.tolist()

    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

# ==== LOCK FUNCTIONS ====
def acquire_lock(key: str, timeout: int) -> bool:
    """
    Acquires a distributed lock for a cache key.

    Args:
        key: The lock key to set in Redis
        timeout: The lock expiration timeout in seconds

    Returns:
        bool: True when the lock is acquired, otherwise False
    """
    return redis_client.set(key, "locked", nx=True, ex=timeout)

def release_lock(key: str) -> None:
    """
    Releases a distributed lock associated with a cache key.

    Args:
        key: The lock key to remove from Redis
    """
    redis_client.delete(key)

# ==== CACHE FUNCTIONS ====
def cached(ttl: int | None = None):
    """
    Decorator to cache GET responses/functions automatically.

    Args:
        ttl: Time-to-live in seconds (if None, uses default DEFAULT_CACHE_TTL)
    """
    if ttl is None:
        ttl = DEFAULT_CACHE_TTL

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Ignore FastAPI infrastructure objects, but keep user_id to isolate
            # cached responses between users with different authorization scopes.
            cache_kwargs = {
                k: v.isoformat() if isinstance(v, (datetime, date)) else v
                for k, v in kwargs.items()
                if not isinstance(v, Request)
            }

            # Sets up a clean and predictable key.
            cache_key = f"cache:{func.__name__}:{cache_kwargs}"

            # Try looking in the cache
            cached_data = get_cached(cache_key)
            if cached_data is not None:
                return cached_data

            # If it does not exist in the cache, execute the route normally.
            result = await func(*args, **kwargs)

            # Saves to cache using the filtered key.
            set_cached(cache_key, result, ttl)
            return result

        return wrapper
    return decorator

def get_cached(key: str) -> dict | None:
    """
    Retrieves a cached value from Redis.

    Args:
        key: The cache key

    Returns:
        dict | None: Deserialized JSON or None if not found
    """
    # Get the key's raw value
    raw_value = redis_client.get(key)

    # If the key doesn't exist, return None
    if raw_value is None:
        return None

    # Deserializes the JSON string back into a Python dictionary.
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as e:
        # ==== STRUCTURED LOGGING ====
        logger.warning(
            f"Failed to deserialize JSON from cache key '{key}', "
            f"Value might be corrupted. Error {e!s}."
        )
        return None

def set_cached(key: str, value: Any, ttl: int | None) -> None:
    """
    Stores a value in Redis cache.

    Args:
        key: The cache key
        value: Data to cache (will be JSON serialized)
        ttl: Time-to-live in seconds (default uses DEFAULT_CACHE_TTL)
    """
    if ttl is None:
        ttl = DEFAULT_CACHE_TTL

    try:
        # Serialize the Python value to JSON string
        serialized_value = json.dumps(value, default=json_serializer)
        # Save on Redis by defining the TTL in secs
        redis_client.set(key, serialized_value, ex=ttl)
    except TypeError as e:
        # If the value has data JSON doesn't accepts, return error
        # ==== STRUCTURED LOGGING ====
        logger.error(
            f"Failed to serialize JSON for cache key '{key}', "
            f"Data type: {type(value)}. Error {e!s}."
        )
    except Exception as e:
        # If any other errors occour, specially Redis ones, return error
        # ==== STRUCTURED LOGGING ====
        logger.error(f"Failed to write to Redis cache for key '{key}'. Error: {e!s}")

def delete_cached(key: str) -> None:
    """
    Deletes a cached value.

    Args:
        key: The cache key
    """
    redis_client.delete(key)

def invalidate_pattern(pattern: str) -> int:
    """
    Invalidates all cache keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "cache:procedures:*")

    Returns:
        int: Number of keys deleted
    """
    total_deleted = 0
    batch = []
    # Recommended batch size to balance memory and network usage
    BATCH_SIZE = 500

    try:
        # Check Redis in a iterative way looking for the pattern input
        for key in redis_client.scan_iter(match=pattern):
            batch.append(key)

            # When the batch hits the max limit, delete, then clean the batch list
            if len(batch) >= BATCH_SIZE:
                deleted_count = redis_client.delete(*batch)
                total_deleted += deleted_count
                batch = []

        # Delete the remaining keys that werent enough to fill a full batch
        if batch:
            deleted_count = redis_client.delete(*batch)
            total_deleted += deleted_count

    except Exception as e:
        # Log error and let the data expire by the defined TTL
        # ==== STRUCTURED LOGGING ====
        logger.error(
            f"Error while invalidating cache pattern '{pattern}', "
            f"Keys deleted before failure: {total_deleted}. Error {e!s}."
        )

    # Else, return total of keys deleted
    return total_deleted