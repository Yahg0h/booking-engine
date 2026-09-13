import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def acquire_lock(key: str, timeout: int) -> bool:
    return redis_client.set(key, "locked", nx=True, ex=timeout)

def release_lock(key: str) -> None:
    redis_client.delete(key)