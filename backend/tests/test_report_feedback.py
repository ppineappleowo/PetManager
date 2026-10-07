import unittest
from unittest.mock import patch
from uuid import uuid4
from app.database.redis import RedisUnavailable
import test_community


class ReportFeedbackTests(unittest.TestCase):
    setUp = test_community.CommunityTests.setUp
    tearDown = test_community.CommunityTests.tearDown
    login = test_community.CommunityTests.login
    token = test_community.CommunityTests.token
    create = test_community.CommunityTests.create

    def test_report_feedback_ownership_filters_and_pagination(self):
        base = '/api/v1/community/me/reports'
        self.assertEqual(self.client.get(base).status_code, 401)
        post = self.create(body='不能出现在反馈中的证据正文').json()
        one = self.db.report(1, 'post', post['id'], '我的原因')
        self.db.report(2, 'post', post['id'], '别人的原因')
        second_post = self.create().json()
        two = self.db.report(1, 'post', second_post['id'], '第二条原因')
        with patch.object(self.limiter, 'consume_attempt', side_effect=RedisUnavailable('offline')):
            response = self.client.get(base+'?limit=1&user_id=2', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        first = response.json()
        self.assertEqual(first['items'][0]['id'], two['id'])
        self.assertEqual(first['next_cursor'], two['id'])
        rest = self.client.get(base+f'?before={two["id"]}&limit=1', headers=self.headers).json()
        self.assertEqual(rest['items'][0]['id'], one['id'])
        self.assertIsNone(rest['next_cursor'])
        data = self.client.get(base, headers=self.headers).json()
        self.assertNotIn('别人的原因', str(data))
        self.assertNotIn('证据正文', str(data))
        self.assertEqual(set(data['items'][0]), {'id','target_type','target_id','reason','status','resolution','note','created_at','resolved_at','target'})
        self.db.resolve_report(one['id'], 2, 'dismiss', '未发现违规')
        for status, expected in [('open', two['id']), ('resolved', one['id'])]:
            rows = self.client.get(base+'?status='+status, headers=self.headers).json()['items']
            self.assertEqual([r['id'] for r in rows], [expected])
        resolved = self.client.get(base+'?status=resolved', headers=self.headers).json()['items'][0]
        self.assertEqual(resolved['note'], '未发现违规')
        self.assertEqual(resolved['target'], f'/posts/{post["id"]}')
        self.assertTrue(resolved['resolved_at'])
        for query in ('status=bad', 'before=0', 'limit=51'):
            self.assertEqual(self.client.get(base+'?'+query, headers=self.headers).status_code, 422)

    def test_report_feedback_hidden_deleted_and_restored_targets(self):
        post = self.create().json()
        comment = self.db.add_comment(post['id'], 2, '保密评论', None, str(uuid4()))
        report = self.db.report(1, 'comment', comment['id'], '评论违规')
        listing = lambda: self.db.report_feedback.listing(1)['items'][0]
        self.db.resolve_report(report['id'], 2, 'hide', '评论含垃圾广告')
        self.assertIsNone(listing()['target'])
        self.assertEqual(listing()['note'], '评论含垃圾广告')
        self.assertNotIn('保密评论', str(listing()))
        self.db.moderate_comment(comment['id'], 2, 'published', '复核恢复', 2)
        self.assertIsNotNone(listing()['target'])
        self.assertEqual(listing()['resolution'], 'hide')  # Historical decision stays unchanged.
        self.db.moderate(post['id'], 2, 'hidden', '帖子下架', post['version'])
        self.assertIsNone(listing()['target'])
        self.db.moderate(post['id'], 2, 'published', '恢复帖子', 2)
        self.assertIsNotNone(listing()['target'])
        self.db.delete_comment(comment['id'], 2)
        self.assertIsNone(listing()['target'])
        report2 = self.db.report(1, 'post', post['id'], '帖子违规')
        self.db.delete(post['id'], 1)
        self.db.resolve_report(report2['id'], 2, 'hide', '内容已删除')
        self.assertIsNone(listing()['target'])
        self.assertEqual(listing()['note'], '内容已删除')
        self.assertEqual(self.db.get(post['id'], admin=True)['status'], 'deleted')

    def test_report_resolution_failure_rolls_back_feedback_content_and_audit(self):
        post = self.create().json()
        report = self.db.report(1, 'post', post['id'], '待核查')
        repo = self.db.interactions.repository
        with patch.object(repo, 'resolve_report', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                self.db.resolve_report(report['id'], 2, 'hide', '确认违规')
        self.assertEqual(self.db.get(post['id'])['status'], 'published')
        self.assertEqual(self.db.moderation_history(post['id']), [])
        self.assertEqual(self.db.report_feedback.listing(1)['items'][0]['status'], 'open')
        self.db.resolve_report(report['id'], 2, 'hide', '确认违规')
        self.db.resolve_report(report['id'], 2, 'hide', '确认违规')
        self.assertEqual(len(self.db.moderation_history(post['id'])), 1)
        self.assertEqual(len(self.db.report_feedback.listing(1)['items']), 1)
