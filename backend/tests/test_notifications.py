import unittest
from unittest.mock import patch
from uuid import uuid4
import test_community


class NotificationTests(unittest.TestCase):
    setUp = test_community.CommunityTests.setUp
    tearDown = test_community.CommunityTests.tearDown
    login = test_community.CommunityTests.login
    token = test_community.CommunityTests.token
    create = test_community.CommunityTests.create

    def test_recipients_retry_privacy_and_read_boundary(self):
        post = self.create().json()['id']
        first = self.db.add_comment(post, 1, '自己评论', None, str(uuid4()))
        self.assertEqual(self.db.notifications.summary(1)['unread_count'], 0)
        key = str(uuid4())
        comment = self.db.add_comment(post, 2, '私密测试正文', first['id'], key)
        self.db.add_comment(post, 2, '私密测试正文', first['id'], key)
        base = '/api/v1/community/me/notifications'
        self.assertEqual(self.client.get(base).status_code, 401)
        self.assertEqual(self.client.get(base+'/summary', headers=self.headers).json()['unread_count'], 1)
        data = self.client.get(base, headers=self.headers).json()['items']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['kind'], 'reply')
        self.assertEqual(data[0]['target'], f'/posts/{post}')
        self.assertNotIn('私密测试正文', str(data))
        self.assertNotIn('phone', data[0]['actor'])
        self.assertEqual(self.client.put(base+f'/{data[0]["id"]}/read', headers=self.bob).status_code, 404)
        boundary = self.db.notifications.summary(1)['latest_id']
        self.db.add_comment(post, 2, '后来评论', None, str(uuid4()))
        self.assertEqual(self.client.put(base+'/read-all', headers=self.headers, json={'through_id': boundary}).status_code, 200)
        self.assertEqual(self.db.notifications.summary(1)['unread_count'], 1)
        page = self.client.get(base+'?limit=1', headers=self.headers).json()
        self.assertIsNotNone(page['next_cursor'])
        rest = self.client.get(base+f'?before={page["next_cursor"]}', headers=self.headers).json()
        self.assertEqual(rest['items'][0]['id'], data[0]['id'])
        self.assertTrue(rest['items'][0]['read'])
        for _ in range(2):
            self.assertEqual(self.client.put(base+f'/{page["items"][0]["id"]}/read', headers=self.headers).status_code, 200)
        self.assertEqual(self.db.notifications.summary(1)['unread_count'], 0)
        # Replying to Bob notifies Bob, but never the acting post owner.
        self.db.add_comment(post, 1, '回复', comment['id'], str(uuid4()))
        self.assertEqual(self.db.notifications.summary(2)['unread_count'], 1)
        self.assertEqual(self.db.notifications.summary(1)['unread_count'], 0)

    def test_notification_failure_rolls_back_comment_and_visibility(self):
        post = self.create().json()
        key = str(uuid4())
        with patch.object(self.db.notifications.repository, 'add', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                self.db.add_comment(post['id'], 2, '保密评论', None, key)
        self.assertEqual(self.db.comments(post['id'])['items'], [])
        self.assertEqual(self.db.notifications.summary(1)['unread_count'], 0)
        comment = self.db.add_comment(post['id'], 2, '保密评论', None, key)
        self.db.delete_comment(comment['id'], 2)
        item = self.db.notifications.listing(1, self.manager)['items'][0]
        self.assertFalse(item['available'])
        self.assertIsNone(item['actor']); self.assertIsNone(item['target'])
        self.db.add_comment(post['id'], 2, '另一个评论', None, str(uuid4()))
        hidden = self.db.moderate(post['id'], 1, 'hidden', '隐藏', post['version'])
        self.assertTrue(all(not n['available'] for n in self.db.notifications.listing(1, self.manager)['items']))
        self.db.moderate(post['id'], 1, 'published', '恢复', hidden['version'])
        self.assertTrue(self.db.notifications.listing(1, self.manager)['items'][0]['available'])
