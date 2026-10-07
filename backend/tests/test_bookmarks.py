import unittest
from concurrent.futures import ThreadPoolExecutor
import test_community


class BookmarkTests(unittest.TestCase):
    setUp = test_community.CommunityTests.setUp
    tearDown = test_community.CommunityTests.tearDown
    login = test_community.CommunityTests.login
    token = test_community.CommunityTests.token
    create = test_community.CommunityTests.create

    def test_bookmark_privacy_order_and_retry(self):
        one = self.create(body='先发布').json()['id']
        two = self.create(body='后发布').json()['id']
        url = lambda post: f'/api/v1/community/posts/{post}/bookmark'
        feed = '/api/v1/community/me/bookmarks'
        self.assertEqual(self.client.get(feed).status_code, 401)
        self.assertEqual(self.client.put(url(one)).status_code, 401)
        self.assertEqual(self.client.get(url(one), headers=self.headers).json(), {'bookmarked': False})
        for post in (two, one, two):
            self.assertEqual(self.client.put(url(post), headers=self.headers).json(), {'bookmarked': True})
        first = self.client.get(feed+'?limit=1', headers=self.headers).json()
        self.assertEqual([p['id'] for p in first['items']], [one])
        self.assertNotIn('user_id', first['items'][0])
        self.assertNotIn('bookmark_id', first['items'][0])
        self.assertEqual(self.client.get(feed, headers=self.bob).json()['items'], [])
        self.assertEqual(self.client.delete(url(one), headers=self.bob).status_code, 200)
        self.assertTrue(self.client.get(url(one), headers=self.headers).json()['bookmarked'])
        second = self.client.get(feed+f'?before={first["next_cursor"]}', headers=self.headers).json()
        self.assertEqual([p['id'] for p in second['items']], [two])
        self.assertIsNone(second['next_cursor'])
        for _ in range(2):
            self.assertEqual(self.client.delete(url(two), headers=self.headers).json(), {'bookmarked': False})
        self.client.put(url(two), headers=self.headers)
        self.assertEqual(self.client.get(feed, headers=self.headers).json()['items'][0]['id'], two)
        self.assertEqual(self.client.get(feed+'?before=0', headers=self.headers).status_code, 422)
        self.assertEqual(self.client.put(url(999999), headers=self.headers).status_code, 404)

    def test_hidden_deleted_and_concurrent_bookmarks(self):
        post = self.create().json()
        user_id = post['author']['id']
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.db.bookmarks.set(user_id, post['id'], True), range(8)))
        self.assertEqual(len(self.db.bookmarks.listing(user_id)['items']), 1)
        hidden = self.db.moderate(post['id'], user_id, 'hidden', '测试', post['version'])
        self.assertEqual(self.db.bookmarks.listing(user_id)['items'], [])
        url = f'/api/v1/community/posts/{post["id"]}/bookmark'
        self.assertEqual(self.client.put(url, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 404)
        self.db.moderate(post['id'], user_id, 'published', '恢复', hidden['version'])
        self.assertEqual(len(self.db.bookmarks.listing(user_id)['items']), 1)
        self.db.delete(post['id'], user_id)
        self.assertEqual(self.db.bookmarks.listing(user_id)['items'], [])
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 200)

    def test_bookmark_limiter_failure_does_not_block_reading(self):
        from app.database.redis import RedisUnavailable
        from unittest.mock import patch
        post = self.create().json()['id']
        url = f'/api/v1/community/posts/{post}/bookmark'
        with patch.object(self.limiter, 'consume_attempt', side_effect=RedisUnavailable('offline')):
            self.assertEqual(self.client.put(url, headers=self.headers).status_code, 503)
            self.assertEqual(self.client.get(url, headers=self.headers).status_code, 200)
            self.assertEqual(self.client.get('/api/v1/community/me/bookmarks', headers=self.headers).status_code, 200)
