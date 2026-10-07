"""关注行为在真实 PostgreSQL 隔离 schema 中验证。"""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4
from app.services.community.posts import CommunityService
from app.database.redis import RedisUnavailable
import test_postgres


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == '1', 'Set RUN_POSTGRES_TESTS=1')
class FollowTests(test_postgres.SchemaTest):
    setUp = test_postgres.PostgresApiTests.setUp
    tearDown = test_postgres.PostgresApiTests.tearDown
    login = test_postgres.PostgresApiTests.login
    token = test_postgres.PostgresApiTests.token
    create = test_postgres.PostgresApiTests.create

    def test_auth_self_idempotency_concurrency_and_counts(self):
        path = '/api/v1/community/users/2/follow'
        self.assertEqual(self.client.put(path).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/community/me/connections').status_code, 401)
        self.assertEqual(self.client.put('/api/v1/community/users/1/follow', headers=self.headers).status_code, 422)
        self.assertEqual(self.client.put('/api/v1/community/users/999/follow', headers=self.headers).status_code, 404)
        for _ in range(2):
            data = self.client.put(path, headers=self.headers)
            self.assertEqual(data.status_code, 200, data.text)
            self.assertTrue(data.json()['following'])
            self.assertEqual(data.json()['follower_count'], 1)
        other = CommunityService(self.url)
        self.addCleanup(other.close)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: (self.db if i % 2 else other).set_follow(1, 2, True), range(8)))
        self.assertEqual(self.db.follow_counts(2)['follower_count'], 1)
        self.assertEqual(self.db.notifications.summary(2)['unread_count'], 1)
        self.assertTrue(self.client.get(path, headers=self.headers).json()['following'])
        self.assertFalse(self.client.get('/api/v1/community/users/1/follow', headers=self.bob).json()['following'])
        for _ in range(2):
            self.assertFalse(self.client.delete(path, headers=self.headers).json()['following'])
        self.assertEqual(self.db.follow_counts(2)['follower_count'], 0)
        self.assertEqual(self.db.notifications.summary(2)['unread_count'], 1)

    def test_notification_failure_rolls_back_follow_and_persists_after_reopen(self):
        with patch.object(self.db.notifications.repository, 'add', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                self.db.set_follow(1, 2, True)
        self.assertFalse(self.db.follow_state(1, 2)['following'])
        self.db.set_follow(1, 2, True)
        other = CommunityService(self.url)
        self.addCleanup(other.close)
        self.assertEqual(other.notifications.summary(2)['unread_count'], 1)
        self.assertEqual(other.notifications.listing(2, self.manager)['items'][0]['target'], '/users/1')

    def test_lists_privacy_pagination_disabled_and_redis_failure(self):
        third = self.manager.create_user('13800138000', 'secret123')['id']
        self.db.set_follow(1, 2, True)
        self.db.set_follow(1, third, True)
        page = self.client.get('/api/v1/community/me/connections?limit=1', headers=self.headers).json()
        self.assertEqual(page['items'][0]['name'], f'宠友_{third}')
        self.assertEqual(set(page['items'][0]), {'id','name','avatar_id','bio','following'})
        page = self.client.get(f"/api/v1/community/me/connections?before={page['next_cursor']}", headers=self.headers).json()
        self.assertEqual([u['id'] for u in page['items']], [2])
        fans = self.client.get('/api/v1/community/me/connections?kind=followers', headers=self.bob).json()
        self.assertEqual([u['id'] for u in fans['items']], [1])
        with self.manager.repository.db:
            self.manager.repository.db.execute('UPDATE users SET disabled=1 WHERE id=2')
        self.assertEqual(self.db.follow_counts(1)['following_count'], 1)
        self.assertEqual(self.client.put('/api/v1/community/users/2/follow', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.delete('/api/v1/community/users/2/follow', headers=self.headers).status_code, 200)
        with patch.object(self.limiter, 'consume_attempt', side_effect=RedisUnavailable('offline')):
            self.assertEqual(self.client.put(f'/api/v1/community/users/{third}/follow', headers=self.headers).status_code, 503)
            self.assertEqual(self.client.get('/api/v1/community/me/connections', headers=self.headers).status_code, 200)
            self.assertEqual(self.login().status_code, 200)

    def test_following_feed_visibility_and_cursor(self):
        own = self.create().json()['id']
        ids = []
        for _ in range(3):
            response = self.client.post('/api/v1/community/posts', headers=self.bob,
                json={'body':'朋友的日常','category':'dog','request_key':str(uuid4())})
            ids.append(response.json()['id'])
        path = '/api/v1/community/me/following/posts'
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get(path, headers=self.headers).json()['items'], [])
        self.db.set_follow(1, 2, True)
        self.db.moderate(ids[1], 1, 'hidden', '测试', 1)
        page = self.client.get(path+'?limit=1', headers=self.headers).json()
        self.assertEqual([p['id'] for p in page['items']], [ids[2]])
        page = self.client.get(path+f"?before={page['next_cursor']}", headers=self.headers).json()
        self.assertEqual([p['id'] for p in page['items']], [ids[0]])
        self.assertEqual(self.client.get(path+'?category=cat', headers=self.headers).json()['items'], [])
        self.assertIn(own, [p['id'] for p in self.client.get('/api/v1/community/posts').json()['items']])
        self.db.delete(ids[0], 2)
        with self.manager.repository.db:
            self.manager.repository.db.execute('UPDATE users SET disabled=1 WHERE id=2')
        self.assertEqual(self.client.get(path, headers=self.headers).json()['items'], [])
