import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import jwt
import fakeredis
from fastapi import FastAPI
from app.core.errors import BusinessError
from fastapi.testclient import TestClient
from app.api.v1 import auth, chat, oss
from app.services.users import UserService, _hash_password
from app.services.ai.turns import TurnService
from app.services.ai.streams import ChatStreams
from app.core.config import Settings
from app.api.schemas.auth_chat import ChatRequest
from app.database.redis_rate_limiter import RedisRateLimiter


class FakeService:
    def __init__(self, path):
        self.turn_store = TurnService(path)
        self.mode = 'normal'
        self.calls = 0
        self.cancelled = False

    async def consult(self, *args):
        self.calls += 1
        try:
            yield {'event': 'status', 'data': {'stage': 'retrieving', 'message': '正在检索'}}
            yield {'event': 'delta', 'data': {'text': '部分回答'}}
            if self.mode == 'slow':
                await asyncio.sleep(100)
            if self.mode == 'error':
                raise RuntimeError('sensitive upstream error')
            yield {'event': 'delta', 'data': {'text': '，完成'}}
        finally:
            self.cancelled = True

    def rag_add_documents(self, documents):
        return len(documents)

    def rag_clear(self):
        pass

    def rag_get_stats(self):
        return {'document_count': 0}


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = UserService(str(Path(self.temp.name) / 'users.db'))
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.limiter = RedisRateLimiter(self.redis, 'test')
        self.settings = Settings(_env_file=None, jwt_secret_key='test-only-secret-key-at-least-32-chars', login_max_attempts=3, login_ip_max_attempts=10)
        self.service = FakeService(str(Path(self.temp.name) / 'pet.db'))
        app = FastAPI()
        app.state.settings = self.settings
        app.state.user_manager = self.manager
        app.state.rate_limiter = self.limiter
        app.state.pet_agent_service = self.service
        app.state.chat_streams = ChatStreams(self.service)
        for router in (auth.router, chat.router, oss.router):
            app.include_router(router, prefix='/api/v1')
        self.client = TestClient(app)
        self.manager.create_user('alice', 'secret123')

    def tearDown(self):
        self.client.close()
        self.redis.close()
        self.manager.close()
        self.service.turn_store.close()
        self.temp.cleanup()

    def login(self, password='secret123'):
        return self.client.post('/api/v1/auth/login', json={'username': 'alice', 'password': password})

    def token(self):
        return {'Authorization': 'Bearer ' + self.login().json()['access_token']}

    def test_validation_and_duplicate_registration(self):
        for data in ({'username': 'x', 'password': 'secret123'}, {'username': 'valid', 'password': '   '}, {'username': 'bad name', 'password': 'secret123'}):
            self.assertEqual(self.client.post('/api/v1/auth/register', json=data).status_code, 422)
        # 注册必须提供手机号，不再接受仅有用户名的请求。
        self.assertEqual(self.client.post('/api/v1/auth/register', json={'username': 'alice', 'password': 'secret123'}).status_code, 422)

    def test_password_change_revokes_old_token(self):
        headers = self.token()
        wrong = self.client.post('/api/v1/auth/password', headers=headers, json={'old_password': 'wrong123', 'new_password': 'newsecret123'})
        self.assertEqual(wrong.status_code, 400)
        changed = self.client.post('/api/v1/auth/password', headers=headers, json={'old_password': 'secret123', 'new_password': 'newsecret123'})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers=headers).status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login('newsecret123').status_code, 200)

    def test_login_uses_database_without_rate_limiter(self):
        del self.client.app.state.rate_limiter
        for _ in range(4):
            self.assertEqual(self.login('wrong123').status_code, 401)
        self.assertEqual(self.login().status_code, 200)
        self.manager.update_profile(1, 'alice', '', '')
        with self.manager.repository.db:
            self.manager.repository.db.execute('UPDATE users SET phone=? WHERE id=1', ('13800138000',))
        response = self.client.post('/api/v1/auth/login', json={'username': '13800138000', 'password': 'secret123'})
        self.assertEqual(response.status_code, 200)

    def test_rate_limit_expiry_and_persistence(self):
        self.assertEqual(self.limiter.consume_attempt([('test', 1)], 60), 0)
        another = RedisRateLimiter(self.redis, 'test')
        self.assertGreater(another.consume_attempt([('test', 1)], 60), 0)
        key = self.limiter.key('test', 60)
        self.redis.zadd(key, {self.redis.zrange(key, 0, 0)[0]: 1})
        self.assertEqual(another.consume_attempt([('test', 1)], 60), 0)

    def test_permissions_and_admin_revocation(self):
        for method, path in [('get', '/api/v1/oss/presign?filename=cat.png'), ('get', '/api/v1/rag/stats'), ('delete', '/api/v1/rag/documents')]:
            self.assertEqual(getattr(self.client, method)(path).status_code, 401)
        headers = self.token()
        self.assertEqual(self.client.post('/api/v1/rag/documents', headers=headers, json={'documents': ['test']}).status_code, 403)
        self.manager.set_role('alice', 'admin')
        self.assertEqual(self.client.post('/api/v1/rag/documents', headers=headers, json={'documents': ['test']}).status_code, 200)
        self.manager.set_role('alice', 'user')
        self.assertEqual(self.client.delete('/api/v1/rag/documents', headers=headers).status_code, 403)
        with patch('app.services.oss_signing._get_oss_client') as factory:
            factory.return_value.presign.return_value = SimpleNamespace(url='https://example.com/put')
            response = self.client.get('/api/v1/oss/presign?filename=cat.png', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertIn('/users/1/', response.json()['accessUrl'])

    def test_malformed_subject_and_missing_expiry(self):
        for claims in ({'sub': 'not-a-number', 'exp': 9999999999}, {'sub': '1'}):
            token = jwt.encode(claims, self.settings.jwt_secret_key, algorithm='HS256')
            self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code, 401)

    def test_http_stream_and_replay(self):
        headers = self.token()
        payload = {'message': '问题', 'thread_id': 'thread', 'request_id': str(uuid4())}
        response = self.client.post('/api/v1/chat/stream', headers=headers, json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn('event: status', response.text)
        self.assertIn('event: done', response.text)
        self.assertIn('completed', response.text)
        again = self.client.post('/api/v1/chat/stream', headers=headers, json=payload)
        self.assertIn('部分回答，完成', again.text)
        self.assertEqual(self.service.calls, 1)


class MigrationTests(unittest.TestCase):
    def test_old_users_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'users.db')
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, created_at TEXT)")
                db.execute('INSERT INTO users VALUES (1, ?, ?, ?)', ('legacy', _hash_password('secret123'), '2026-01-01'))
            db.close()
            manager = UserService(path)
            try:
                user = manager.authenticate('legacy', 'secret123')
                self.assertEqual(user['role'], 'user')
                self.assertEqual(user['token_version'], 0)
                self.assertEqual(user['created_at'], '2026-01-01')
            finally:
                manager.close()


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = FakeService(str(Path(self.temp.name) / 'pet.db'))
        self.streams = ChatStreams(self.service, timeout=1)
        self.request = ChatRequest(message='问题', thread_id='same-thread', request_id=uuid4())

    async def asyncTearDown(self):
        await self.streams.close()
        self.service.turn_store.close()
        self.temp.cleanup()

    async def collect(self, key, run):
        return ''.join([frame async for frame in self.streams.stream(key, run)])

    async def test_stop_isolation_and_retry(self):
        self.service.mode = 'slow'
        key, run = self.streams.start('1', self.request)
        await asyncio.sleep(0.01)
        with self.assertRaises(BusinessError) as error:
            await self.streams.stop('2', str(self.request.request_id))
        self.assertEqual(error.exception.status_code, 404)
        self.assertFalse(run['task'].done())
        await self.streams.stop(*key)
        self.assertTrue(self.service.cancelled)
        self.assertIn('cancelled', await self.collect(key, run))
        self.assertEqual(self.service.turn_store.get(*key)['answer'], '部分回答')
        self.service.mode = 'normal'
        key, run = self.streams.start('1', self.request)
        self.assertIn('completed', await self.collect(key, run))
        self.assertEqual(len(self.service.turn_store.messages('1', 'same-thread')), 2)

    async def test_error_and_timeout(self):
        for mode in ('error', 'slow'):
            self.service.mode = mode
            key, run = self.streams.start('1', self.request)
            output = await self.collect(key, run)
            self.assertIn('event: error', output)
            self.assertIn('failed', output)
            self.assertNotIn('sensitive upstream error', output)
            self.assertEqual(self.service.turn_store.get(*key)['status'], 'failed')

    async def test_disconnect_cancels_and_busy_guard(self):
        self.service.mode = 'slow'
        key, run = self.streams.start('1', self.request)
        stream = self.streams.stream(key, run)
        await anext(stream)
        await asyncio.sleep(0.01)
        with self.assertRaises(BusinessError):
            self.streams.start('1', self.request)
        await stream.aclose()
        self.assertEqual(self.service.turn_store.get(*key)['status'], 'cancelled')
        self.assertFalse(self.streams.active)

    async def test_completed_replay_and_id_mismatch(self):
        key, run = self.streams.start('1', self.request)
        await self.collect(key, run)
        key, replay = self.streams.start('1', self.request)
        self.assertIn('部分回答，完成', await self.collect(key, replay))
        self.assertEqual(self.service.calls, 1)
        self.request.message = '不同内容'
        with self.assertRaises(BusinessError):
            self.streams.start('1', self.request)

    async def test_same_thread_isolated_by_user(self):
        first = self.streams.start('1', self.request)
        second = self.streams.start('2', self.request)
        await asyncio.gather(self.collect(*first), self.collect(*second))
        self.service.turn_store.delete('1', 'same-thread')
        self.assertEqual(self.service.turn_store.messages('1', 'same-thread'), [])
        self.assertEqual(len(self.service.turn_store.messages('2', 'same-thread')), 2)

    async def test_immediate_stop_and_cancelled_scope_disconnect(self):
        from anyio import CancelScope
        key, run = self.streams.start('1', self.request)
        await self.streams.stop(*key)
        self.assertEqual(self.service.turn_store.get(*key)['status'], 'cancelled')
        self.service.mode = 'slow'
        key, run = self.streams.start('1', self.request)
        stream = self.streams.stream(key, run)
        await anext(stream)
        await asyncio.sleep(0.01)
        with CancelScope() as scope:
            scope.cancel()
            await stream.aclose()
        self.assertFalse(self.streams.active)
        self.assertEqual(self.service.turn_store.get(*key)['status'], 'cancelled')


class AgentEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_context_and_internal_model_filter(self):
        from app.services.ai.agent import PetAgentService
        service = PetAgentService.__new__(PetAgentService)
        service.get_messages = lambda *args: [
            {'role': 'user', 'content': '旧问题'},
            {'role': 'assistant', 'content': '旧答案'},
            {'role': 'assistant', 'content': '失败片段', 'status': 'failed'},
            {'role': 'user', 'content': '当前问题', 'status': 'running'},
        ]
        captured = []
        async def events(payload, **kwargs):
            captured.extend(payload['messages'])
            yield {'event': 'on_tool_start'}
            yield {'event': 'on_chat_model_stream', 'metadata': {'langgraph_node': 'tools'}, 'data': {'chunk': SimpleNamespace(content='内部查询')}}
            yield {'event': 'on_tool_end'}
            yield {'event': 'on_chat_model_stream', 'metadata': {'langgraph_node': 'model'}, 'data': {'chunk': SimpleNamespace(content=[{'type': 'text', 'text': '正式答案'}])}}
        service.agent = SimpleNamespace(astream_events=events)
        output = [event async for event in service.consult('当前问题', '', 't', '1')]
        self.assertEqual([message.content for message in captured], ['旧问题', '旧答案', '当前问题'])
        self.assertEqual([event['data']['text'] for event in output if event['event'] == 'delta'], ['正式答案'])
        self.assertEqual([event['data']['stage'] for event in output if event['event'] == 'status'], ['retrieving', 'thinking', 'generating'])


if __name__ == '__main__':
    unittest.main()
