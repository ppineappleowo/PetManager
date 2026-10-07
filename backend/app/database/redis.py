"""Redis 连接与缓存适配器。仅处理短期数据，不写入 SQLite/Chroma。"""
import json

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry


class RedisUnavailable(RuntimeError):
    pass


class RedisService:
    def __init__(self, client, namespace="baichongji"):
        self.client = client
        self.namespace = namespace

    @classmethod
    def from_settings(cls, settings):
        client = Redis.from_url(
            settings.redis_url.get_secret_value(), decode_responses=True,
            socket_connect_timeout=settings.redis_connect_timeout,
            socket_timeout=settings.redis_socket_timeout,
            max_connections=settings.redis_max_connections,
            health_check_interval=30,
            # 不自动重放结果未知的写入操作。
            retry=Retry(NoBackoff(), 0),
        )
        return cls(client, settings.redis_namespace)

    def ping(self):
        try:
            return bool(self.client.ping())
        except RedisError:
            raise RedisUnavailable("Redis 服务暂不可用") from None

    def cache_key(self, key):
        return f"{self.namespace}:cache:{key}"

    def get_json(self, key):
        """缓存不可用或数据损坏视为未命中，调用者负责读取业务存储。"""
        try:
            value = self.client.get(self.cache_key(key))
            return json.loads(value) if value is not None else None
        except (RedisError, ValueError, TypeError):
            return None

    def set_json(self, key, value, ttl):
        if ttl <= 0:
            raise ValueError("缓存 TTL 必须大于零")
        payload = json.dumps(value, ensure_ascii=False)
        try:
            return bool(self.client.set(self.cache_key(key), payload, ex=ttl))
        except RedisError:
            return False

    def delete_cache(self, key):
        try:
            self.client.delete(self.cache_key(key))
            return True
        except RedisError:
            return False

    def close(self):
        self.client.close()
        self.client.connection_pool.disconnect()
