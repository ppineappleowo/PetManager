from app.core.errors import BusinessError
from app.database.redis import RedisUnavailable

def consume(limiter, scopes, window):
    try:
        return limiter.consume_attempt(scopes, window)
    except RedisUnavailable:
        raise BusinessError(503, '限流服务暂不可用，请稍后重试', headers={'Retry-After': '5'}) from None

def enforce_limit(manager, scopes, window):
    retry = consume(manager, scopes, window)
    if retry:
        raise BusinessError(429, '操作过于频繁，请稍后重试', headers={'Retry-After': str(retry)})
