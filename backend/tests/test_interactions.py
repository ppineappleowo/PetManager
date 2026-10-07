import sqlite3
from contextlib import closing
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from app.services.community.posts import CommunityService
from app.database.redis import RedisUnavailable
import test_community


class InteractionTests(unittest.TestCase):
    setUp = test_community.CommunityTests.setUp
    tearDown = test_community.CommunityTests.tearDown
    login = test_community.CommunityTests.login
    token = test_community.CommunityTests.token
    create = test_community.CommunityTests.create

    def comment(self, post_id, headers=None, **values):
        return self.client.post(f'/api/v1/community/posts/{post_id}/comments', headers=headers or self.headers,
            json={'body':'评论内容','request_key':str(uuid4()),**values})

    def test_comment_reply_retry_privacy_delete_and_pagination(self):
        post = self.create().json()['id']
        key = str(uuid4())
        comment = self.comment(post,request_key=key).json()
        self.assertEqual(self.comment(post,request_key=key).json()['id'],comment['id'])
        self.assertEqual(self.comment(post,request_key=key,body='different').status_code,409)
        reply = self.comment(post,headers=self.bob,reply_to=comment['id']).json()
        self.assertEqual(reply['reply_author']['name'],'alice')
        other_post = self.create().json()['id']
        self.assertEqual(self.comment(other_post,reply_to=comment['id']).status_code,404)
        self.assertEqual(self.comment(post,body='   ').status_code,422)
        self.assertEqual(self.comment(post,body='a'*1001).status_code,422)
        url = f'/api/v1/community/posts/{post}/comments'
        first = self.client.get(url+'?limit=1').json()
        self.assertEqual(first['next_cursor'],comment['id'])
        second = self.client.get(url+f"?after={first['next_cursor']}").json()
        self.assertEqual(second['items'][0]['id'],reply['id'])
        self.assertNotIn('user_id',str(first)); self.assertNotIn('request_key',str(first))
        self.assertEqual(self.client.delete(f"/api/v1/community/comments/{comment['id']}",headers=self.bob).status_code,404)
        self.assertEqual(self.client.delete(f"/api/v1/community/comments/{comment['id']}",headers=self.headers).status_code,200)
        items = self.client.get(url).json()['items']
        self.assertEqual(items[0]['body'],''); self.assertIsNone(items[0]['author'])
        self.assertEqual(items[1]['body'],'评论内容')
        self.assertIsNone(items[1]['reply_author']['id'])
        self.assertEqual(self.comment(post,reply_to=comment['id']).status_code,404)
        self.assertEqual(self.client.get(f'/api/v1/community/posts/{post}').json()['comment_count'],1)

    def test_like_idempotence_concurrency_and_counts(self):
        post = self.create().json()['id']; url = f'/api/v1/community/posts/{post}/like'
        self.assertEqual(self.client.put(url).status_code,401)
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _:self.db.like(post,1,True),range(12)))
        self.assertTrue(all(r['like_count']==1 for r in results))
        self.assertEqual(self.client.put(url,headers=self.headers).json()['like_count'],1)
        self.assertEqual(self.client.put(url,headers=self.bob).json()['like_count'],2)
        self.assertTrue(self.client.get(f'/api/v1/community/posts/{post}/interaction',headers=self.headers).json()['liked'])
        self.assertEqual(self.client.delete(url,headers=self.headers).json()['like_count'],1)
        self.assertEqual(self.client.delete(url,headers=self.headers).json()['like_count'],1)
        self.assertEqual(self.client.get('/api/v1/community/posts').json()['items'][0]['like_count'],1)

    def test_report_permissions_dedup_snapshot_resolution_and_deleted_target(self):
        post = self.create().json()['id']; comment = self.comment(post).json()['id']
        payload = {'target_type':'comment','target_id':comment,'reason':'广告内容'}
        self.assertEqual(self.client.post('/api/v1/community/reports',json=payload).status_code,401)
        report = self.client.post('/api/v1/community/reports',headers=self.bob,json=payload).json()
        self.assertEqual(self.client.post('/api/v1/community/reports',headers=self.bob,json=payload).json()['id'],report['id'])
        self.assertEqual(self.client.get('/api/v1/community/admin/reports',headers=self.headers).status_code,403)
        self.manager.set_role('bob','admin')
        records = self.client.get('/api/v1/community/admin/reports',headers=self.bob).json()
        self.assertEqual(records['total'],1); self.assertEqual(records['items'][0]['snapshot']['body'],'评论内容')
        resolution = {'action':'hide','note':'已核实为广告'}
        url = f"/api/v1/community/admin/reports/{report['id']}"
        self.assertEqual(self.client.patch(url,headers=self.bob,json=resolution).status_code,200)
        self.assertEqual(self.client.patch(url,headers=self.bob,json=resolution).status_code,200)
        self.assertEqual(self.client.patch(url,headers=self.bob,json={'action':'dismiss','note':'不同结论'}).status_code,409)
        self.assertEqual(self.client.get(f'/api/v1/community/posts/{post}/comments').json()['items'][0]['body'],'')
        admin_comment = self.client.get('/api/v1/community/admin/comments',headers=self.bob).json()['items'][0]
        self.assertEqual(len(admin_comment['audit']),1)
        self.assertEqual(self.client.patch(f'/api/v1/community/admin/comments/{comment}',headers=self.bob,json={'status':'published','reason':'复核恢复','version':admin_comment['version']}).status_code,200)
        self.assertEqual(self.client.get(f'/api/v1/community/posts/{post}/comments').json()['items'][0]['body'],'评论内容')
        second = self.client.post('/api/v1/community/reports',headers=self.headers,json={'target_type':'post','target_id':post,'reason':'需核查'}).json()['id']
        self.client.delete(f'/api/v1/community/posts/{post}',headers=self.headers)
        self.assertEqual(self.client.patch(f'/api/v1/community/admin/reports/{second}',headers=self.bob,json=resolution).status_code,200)
        self.assertEqual(self.db.get(post,admin=True)['status'],'deleted')

    def test_hidden_post_and_redis_outage_disabled_user(self):
        post = self.create().json()['id']
        with patch.object(self.limiter,'consume_attempt',side_effect=RedisUnavailable('private')):
            self.assertEqual(self.comment(post).status_code,503)
            self.assertEqual(self.client.put(f'/api/v1/community/posts/{post}/like',headers=self.headers).status_code,503)
            self.assertEqual(self.client.get(f'/api/v1/community/posts/{post}/comments').status_code,200)
            self.assertEqual(self.login().status_code,200)
        self.db.moderate(post,2,'hidden','下架',1)
        self.assertEqual(self.comment(post).status_code,404)
        self.assertEqual(self.client.put(f'/api/v1/community/posts/{post}/like',headers=self.headers).status_code,404)
        self.assertEqual(self.client.get(f'/api/v1/community/posts/{post}/comments').status_code,404)
        self.manager.admin_update(1,2,disabled=True)
        self.assertEqual(self.comment(post).status_code,401)

    def test_migration_backups_preserve_posts_and_run_once(self):
        post = self.create().json()['id']
        with self.db.repository.db:
            for table in ('comment_moderation','reports','post_likes','comments'):
                self.db.repository.db.execute('DROP TABLE '+table)
            self.db.repository.db.execute('DELETE FROM community_migrations WHERE version=2')
        self.db.close()
        path = Path(self.temp.name)/'community.db'
        self.db = CommunityService(path); self.client.app.state.community_store = self.db
        self.assertEqual(self.db.get(post)['body'],'今天的小宠日常')
        backups = sorted((path.parent/'backups').glob('*.db'),key=lambda p:p.stat().st_mtime_ns)
        with closing(sqlite3.connect(backups[-1])) as backup:
            self.assertEqual(backup.execute('SELECT body FROM posts WHERE id=?',(post,)).fetchone()[0],'今天的小宠日常')
            self.assertIsNone(backup.execute('SELECT 1 FROM community_migrations WHERE version=2').fetchone())
        self.db.close(); self.db = CommunityService(path); self.client.app.state.community_store = self.db
        self.assertEqual(len(list((path.parent/'backups').glob('*.db'))),len(backups))
