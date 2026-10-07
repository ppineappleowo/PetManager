"""Redis 滑动窗口限流；多范围校验与预占在一段 Lua 中原子执行。"""
import hashlib
from uuid import uuid4

from redis.exceptions import RedisError
from app.database.redis import RedisUnavailable


SCRIPT = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local window = tonumber(ARGV[1])
local retry = 0
for i, key in ipairs(KEYS) do
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
    local count = redis.call('ZCARD', key)
    local limit = tonumber(ARGV[i + 2])
    if count >= limit then
        local oldest = redis.call('ZRANGE', key, count - limit, count - limit, 'WITHSCORES')
        retry = math.max(retry, math.ceil((tonumber(oldest[2]) + window - now) / 1000))
    end
end
if retry > 0 then return retry end
for _, key in ipairs(KEYS) do
    redis.call('ZADD', key, now, ARGV[2])
    redis.call('PEXPIRE', key, window)
end
return 0
"""


class RedisRateLimiter:
    def __init__(self, client, namespace="baichongji"):
        self.client = client
        self.namespace = namespace
        self.script = client.register_script(SCRIPT)

    def key(self, scope, window):
        digest = hashlib.sha256(scope.encode()).hexdigest()
        # 同一 hash tag 保证多范围脚本的 key 同槽；不在 key 中暴露手机号/IP。
        return f"{self.namespace}:{{rate-limit}}:{window}:{digest}"

    def consume_attempt(self, scopes, window):
        if not scopes or window <= 0 or any(limit <= 0 for _, limit in scopes):
            raise ValueError("限流范围、额度和窗口必须有效")
        if len({scope for scope, _ in scopes}) != len(scopes):
            raise ValueError("限流范围不能重复")
        try:
            return int(self.script(
                keys=[self.key(scope, window) for scope, _ in scopes],
                args=[window * 1000, uuid4().hex, *[limit for _, limit in scopes]],
            ))
        except RedisError:
            # 安全限流故障不可静默放行，也不回退到另一个数据库。
            raise RedisUnavailable("限流服务暂不可用") from None
