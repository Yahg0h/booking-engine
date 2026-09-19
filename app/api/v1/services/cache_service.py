"""
Redis-backed helpers used to coordinate booking locks.
"""

import redis

from app.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

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