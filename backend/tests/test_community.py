import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from app.api.v1 import community
from app.services.community.posts import CommunityService
from app.services.media import prepare_image
from app.database.redis import RedisUnavailable
import test_features


class MemoryMedia:
    def __init__(self):
        self.items = {}

    def put(self, media_id, images):
        self.items[media_id] = images

    def get(self, media_id, thumbnail=False):
        return self.items[media_id][int(thumbnail)]

    def delete(self, media_id):
        self.items.pop(media_id, None)


class CommunityTests(unittest.TestCase):
    def setUp(self):
        test_features.AuthTests.setUp(self)
        self.db = CommunityService(Path(self.temp.name) / 'community.db')
        self.media = MemoryMedia()
        self.client.app.state.community_store = self.db
        self.client.app.state.community_media = self.media
        self.client.app.include_router(community.router, prefix='/api/v1')
        self.headers = self.token()
        self.manager.create_user('bob', 'secret123')
        self.bob = {'Authorization': 'Bearer ' + self.client.post('/api/v1/auth/login', json={'username': 'bob', 'password': 'secret123'}).json()['access_token']}

    def tearDown(self):
        self.db.close()
        test_features.AuthTests.tearDown(self)

    login = test_features.AuthTests.login
    token = test_features.AuthTests.token

    def create(self, **values):
        data = {'body': '今天的小宠日常', 'category': 'cat', 'request_key': str(uuid4()), **values}
        return self.client.post('/api/v1/community/posts', headers=self.headers, json=data)

    @staticmethod
    def picture():
        buffer = BytesIO()
        Image.new('RGB', (120, 80), '#aaccee').save(buffer, 'PNG')
        return buffer.getvalue()

    def upload(self, headers=None):
        response = self.client.post('/api/v1/community/media', headers=headers or self.headers, content=self.picture())
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def test_public_feed_privacy_pagination_and_ownership(self):
        first = self.create().json()
        second = self.create(category='dog').json()
        feed = self.client.get('/api/v1/community/posts?limit=1').json()
        self.assertEqual(feed['items'][0]['id'], second['id'])
        self.assertNotIn('phone', str(feed))
        self.assertEqual(set(feed['items'][0]['author']), {'id', 'name', 'avatar_id'})
        self.create(category='bird')
        next_page = self.client.get(f"/api/v1/community/posts?before={feed['next_cursor']}").json()
        self.assertEqual([p['id'] for p in next_page['items']], [first['id']])
        self.assertEqual(len(self.client.get('/api/v1/community/posts?category=dog').json()['items']), 1)
        self.assertEqual(self.client.get(f"/api/v1/community/mine/{first['id']}", headers=self.bob).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/community/posts/{first['id']}", headers=self.bob).status_code, 404)
        self.assertEqual(self.client.post('/api/v1/community/posts', json={}).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/community/admin/posts', headers=self.bob).status_code, 403)
        self.manager.update_profile(1, '13700000000', '', '')
        public = self.client.get(f"/api/v1/community/posts/{first['id']}").json()
        self.assertEqual(public['author']['name'], '宠友_1')
        self.assertNotIn('13700000000', str(public))

    def test_retry_version_and_persistence(self):
        key = str(uuid4())
        first = self.create(request_key=key, tags=[' 日常 ', '日常']).json()
        self.assertEqual(first['tags'], ['日常'])
        self.assertEqual(self.create(request_key=key, tags=[' 日常 ', '日常']).json()['id'], first['id'])
        self.assertEqual(self.create(request_key=key, body='不同内容').status_code, 409)
        edit = {'body': '编辑过的内容', 'category': 'cat', 'version': 1}
        url = f"/api/v1/community/posts/{first['id']}"
        self.assertEqual(self.client.put(url, headers=self.bob, json=edit).status_code, 404)
        result = self.client.put(url, headers=self.headers, json=edit).json()
        self.assertEqual(result['created_at'], first['created_at'])
        self.assertEqual(self.client.put(url, headers=self.headers, json=edit).status_code, 409)
        self.db.close()
        self.db = CommunityService(Path(self.temp.name) / 'community.db')
        self.client.app.state.community_store = self.db
        self.assertEqual(self.client.get(url).json()['body'], '编辑过的内容')

    def test_images_validation_ownership_and_limit(self):
        invalid = self.client.post('/api/v1/community/media', headers=self.headers, content=b'<svg>not a picture</svg>')
        self.assertEqual(invalid.status_code, 422)
        image = self.upload(self.bob)
        self.assertEqual(self.create(images=[image]).status_code, 422)
        self.assertEqual(self.client.get('/api/v1/community/media/' + image, headers=self.headers).status_code, 404)
        images = [self.upload() for _ in range(9)]
        post = self.create(images=images).json()
        self.assertEqual(len(post['images']), 9)
        response = self.client.get(f"/api/v1/community/posts/{post['id']}/images/{images[0]}?thumbnail=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(Image.open(BytesIO(response.content)).format, 'WEBP')
        self.assertEqual(self.create(images=images + [image]).status_code, 422)
        self.assertEqual(self.create(images=[images[0], images[0]]).status_code, 422)
        self.assertEqual(self.create(body='  ').status_code, 422)
        self.assertEqual(self.create(tags=['a' * 13]).status_code, 422)

    def test_moderation_edit_cannot_republish_and_delete_cannot_restore(self):
        image = self.upload()
        post = self.create(images=[image]).json()
        self.manager.set_role('bob', 'admin')
        admin_url = f"/api/v1/community/admin/posts/{post['id']}"
        public_url = f"/api/v1/community/posts/{post['id']}"
        response = self.client.patch(admin_url, headers=self.bob, json={'status':'hidden','reason':'需核查','version':1})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.assertEqual(self.client.get(public_url + '/images/' + image).status_code, 404)
        edited = self.client.put(public_url, headers=self.headers, json={'body':'修改内容','category':'cat','images':[image],'version':2}).json()
        self.assertEqual(edited['status'], 'hidden')
        self.assertEqual(len(self.client.get(admin_url, headers=self.bob).json()['audit']), 1)
        self.assertEqual(self.client.patch(admin_url, headers=self.bob, json={'status':'published','reason':'通过','version':3}).status_code, 200)
        self.assertEqual(self.client.get(public_url).status_code, 200)
        self.assertEqual(self.client.delete(public_url, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.assertEqual(self.client.patch(admin_url, headers=self.bob, json={'status':'published','reason':'通过','version':5}).status_code, 409)

    def test_cleanup_preserves_referenced_and_recent_media(self):
        used = self.upload(); abandoned = self.upload()
        self.create(images=[used])
        with self.db.repository.db:
            self.db.repository.db.execute("UPDATE media SET touched_at=datetime('now','-2 days')")
        recent = self.upload()
        self.assertEqual(self.db.clean_media(self.media), 1)
        self.assertIn(used, self.media.items)
        self.assertIn(recent, self.media.items)
        self.assertNotIn(abandoned, self.media.items)

    def test_redis_failure_and_disabled_author(self):
        post = self.create().json()
        with patch.object(self.limiter, 'consume_attempt', side_effect=RedisUnavailable('internal')):
            self.assertEqual(self.create().status_code, 503)
            self.assertEqual(self.client.get('/api/v1/community/posts').status_code, 200)
        self.manager.admin_update(1, 2, disabled=True)
        self.assertEqual(self.create().status_code, 401)
        self.assertEqual(self.client.get(f"/api/v1/community/posts/{post['id']}").status_code, 200)


class IsolationTests(unittest.TestCase):
    def test_ai_failure_does_not_prevent_community_or_users(self):
        from app import main
        from pydantic import SecretStr
        with tempfile.TemporaryDirectory() as temp:
            settings = SimpleNamespace(database_url=SecretStr('postgresql://test'), resources_dir=Path(temp), users_db_path=str(Path(temp)/'users.db'), redis_namespace='test', chat_timeout_seconds=30,rag_chunk_size=500,rag_chunk_overlap=100)
            redis = MagicMock()
            from app.services.users import UserService
            with patch.object(main, 'initialize_database'), patch.object(main,'UserService',side_effect=lambda **kwargs:UserService(str(Path(temp)/'users.db'))), patch.object(main,'CommunityService',side_effect=lambda url:CommunityService(Path(temp)/'community.db')), patch.object(main, 'get_settings', return_value=settings), patch.object(main.RedisService, 'from_settings', return_value=redis), patch.object(main, '_setup_dashscope', side_effect=RuntimeError('secret')):
                app = FastAPI(lifespan=main.lifespan)
                app.include_router(community.router, prefix='/api/v1')
                with TestClient(app) as client:
                    self.assertEqual(app.state.ai_status, 'idle')
                    app.state.initialize_ai()
                    self.assertEqual(app.state.ai_status, 'unavailable')
                    self.assertEqual(client.get('/api/v1/community/posts').json()['items'], [])
                    self.assertIsNotNone(app.state.user_manager.create_user('valid', 'secret123'))
