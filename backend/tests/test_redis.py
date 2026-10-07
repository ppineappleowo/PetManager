import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

import fakeredis
from redis import Redis
from redis.exceptions import ConnectionError

from app.database.redis_rate_limiter import RedisRateLimiter
from app.database.redis import RedisService, RedisUnavailable
import test_features


class RedisTests(unittest.TestCase):
    def setUp(self):
        self.client = fakeredis.FakeRedis(decode_responses=True)
        self.addCleanup(self.client.close)
        self.limiter = RedisRateLimiter(self.client, 'test')

    def test_multi_scope_rejection_does_not_consume_other_scope(self):
        self.assertEqual(self.limiter.consume_attempt([('ip', 1)], 60), 0)
        self.assertGreater(self.limiter.consume_attempt([('ip', 1), ('user', 1)], 60), 0)
        self.assertEqual(self.limiter.consume_attempt([('user', 1)], 60), 0)

    def test_shared_server_concurrent_limit(self):
        other = RedisRateLimiter(self.client, 'test')
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: (self.limiter if i % 2 else other).consume_attempt([('same', 5)], 60), range(24)))
        self.assertEqual(results.count(0), 5)
        self.assertGreater(self.client.ttl(self.limiter.key('same', 60)), 0)

    def test_namespaces_and_windows_are_independent(self):
        self.assertEqual(self.limiter.consume_attempt([('same', 1)], 60), 0)
        self.assertEqual(self.limiter.consume_attempt([('same', 1)], 3600), 0)
        self.assertEqual(RedisRateLimiter(self.client, 'other').consume_attempt([('same', 1)], 60), 0)

    def test_reduced_limit_retry_waits_for_enough_slots(self):
        for _ in range(3):
            self.limiter.consume_attempt([('same', 3)], 60)
        key = self.limiter.key('same', 60)
        members = self.client.zrange(key, 0, -1)
        seconds, micros = self.client.time()
        now = seconds * 1000 + micros // 1000
        self.client.zadd(key, dict(zip(members, [now - 50000, now - 30000, now - 10000])))
        self.assertGreaterEqual(self.limiter.consume_attempt([('same', 1)], 60), 49)

    def test_cache_expiry_isolation_and_failure_policy(self):
        service = RedisService(self.client, 'test')
        self.assertTrue(service.set_json('item', {'name': '猫'}, 30))
        self.assertEqual(service.get_json('item'), {'name': '猫'})
        self.assertGreater(self.client.ttl(service.cache_key('item')), 0)
        self.assertIsNone(RedisService(self.client, 'other').get_json('item'))
        self.assertTrue(service.delete_cache('item'))
        self.assertIsNone(service.get_json('item'))
        with patch.object(self.client, 'get', side_effect=ConnectionError('private credentials')):
            self.assertIsNone(service.get_json('item'))
        with patch.object(self.client, 'ping', side_effect=ConnectionError('private credentials')):
            with self.assertRaisesRegex(RedisUnavailable, '^Redis 服务暂不可用$'):
                service.ping()


class RedisRouteTests(unittest.TestCase):
    setUp = test_features.AuthTests.setUp
    tearDown = test_features.AuthTests.tearDown
    login = test_features.AuthTests.login
    token = test_features.AuthTests.token

    def test_outage_rejects_auth_operations_but_profile_remains_readable(self):
        token = self.token()
        with patch.object(self.limiter, 'script', side_effect=ConnectionError('private connection')):
            requests = [
                self.client.post('/api/v1/auth/register', json={'phone': '13900139000', 'password': 'secret123'}),
                self.client.post('/api/v1/auth/password', headers=token, json={'old_password': 'secret123', 'new_password': 'newsecret123'}),
            ]
            for response in requests:
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers['Retry-After'], '5')
                self.assertNotIn('private', response.text)
            self.assertEqual(self.client.get('/api/v1/auth/me', headers=token).status_code, 200)
            self.assertEqual(self.login().status_code, 200)
            self.assertEqual(self.login('wrong123').status_code, 401)
        tables = {row[0] for row in self.manager.repository.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn('auth_attempts', tables)


class RedisLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.database_setup = patch('app.main.initialize_database')
        self.database_setup.start()
        self.addCleanup(self.database_setup.stop)
    async def test_redis_outage_allows_startup_and_closes_resources(self):
        from fastapi import FastAPI
        from app import main
        service = MagicMock()
        service.ping.side_effect = RedisUnavailable('Redis 服务暂不可用')
        with patch.object(main.RedisService, 'from_settings', return_value=service), patch.object(main, 'UserService') as users, patch.object(main, 'CommunityService') as community:
            app = FastAPI()
            async with main.lifespan(app):
                self.assertIs(app.state.user_manager, users.return_value)
                self.assertIs(app.state.community_store, community.return_value)
            service.close.assert_called_once()
            users.return_value.close.assert_called_once()
            community.return_value.close.assert_called_once()

    async def test_lifecycle_closes_resources_and_health_reports_outage(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app import main
        service = MagicMock()
        streams = MagicMock()
        streams.close = AsyncMock()
        app = FastAPI()
        with patch.object(main.RedisService, 'from_settings', return_value=service), \
             patch.object(main, '_setup_dashscope'), patch.object(main, 'RAGManager'), \
             patch.object(main, 'UserService') as users, patch.object(main, 'CommunityService'), patch.object(main, 'PetAgentService') as agent, \
             patch.object(main, 'ChatStreams', return_value=streams):
            async with main.lifespan(app):
                self.assertIs(app.state.redis_service, service)
                self.assertIsInstance(app.state.rate_limiter, RedisRateLimiter)
                agent.assert_not_called()
                app.state.initialize_ai()
            service.close.assert_called_once()
            users.return_value.close.assert_called_once()
            agent.return_value.close.assert_called_once()
            streams.close.assert_awaited_once()
        main.app.dependency_overrides[main.get_redis_service] = lambda: service
        try:
            client = TestClient(main.app)
            self.addCleanup(client.close)
            self.assertEqual(client.get('/health/redis').status_code, 200)
            service.ping.side_effect = RedisUnavailable('private')
            response = client.get('/health/redis')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private', response.text)
        finally:
            main.app.dependency_overrides.pop(main.get_redis_service, None)


@unittest.skipUnless(os.getenv('TEST_REDIS_URL'), 'Set TEST_REDIS_URL to test a real Redis instance')
class RealRedisTests(unittest.TestCase):
    def test_real_lua_concurrency_cache_and_expiry(self):
        import time
        client = Redis.from_url(os.environ['TEST_REDIS_URL'], decode_responses=True)
        namespace = 'test-' + uuid4().hex
        limiter = RedisRateLimiter(client, namespace)
        service = RedisService(client, namespace)
        try:
            service.ping()
            with ThreadPoolExecutor(max_workers=10) as pool:
                result = list(pool.map(lambda _: limiter.consume_attempt([('ip', 5), ('user', 5)], 2), range(30)))
            self.assertEqual(result.count(0), 5)
            self.assertTrue(service.set_json('key', {'ok': True}, 1))
            self.assertEqual(service.get_json('key'), {'ok': True})
            time.sleep(2.1)
            self.assertIsNone(service.get_json('key'))
            self.assertEqual(limiter.consume_attempt([('ip', 5), ('user', 5)], 2), 0)
        finally:
            keys = list(client.scan_iter(match=namespace + ':*'))
            if keys:
                client.delete(*keys)
            service.close()
