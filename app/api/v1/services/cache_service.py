import redis

from app.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

def acquire_lock(key: str, timeout: int) -> bool:
    return redis_client.set(key, "locked", nx=True, ex=timeout)

def release_lock(key: str) -> None:
    redis_client.delete(key)