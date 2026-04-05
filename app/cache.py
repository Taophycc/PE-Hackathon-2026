import os
import redis

_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            decode_responses=True,
        )
    return _redis_client


def cache_get(key):
    try:
        return get_redis().get(key)
    except Exception:
        return None


def cache_set(key, value, ttl=3600):
    try:
        get_redis().setex(key, ttl, value)
    except Exception:
        pass


def cache_delete(key):
    try:
        get_redis().delete(key)
    except Exception:
        pass
