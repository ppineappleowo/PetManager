import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.api.dependencies import get_avatar_media
import test_community


class PublicProfilesTests(unittest.TestCase):
    setUp = test_community.CommunityTests.setUp
    tearDown = test_community.CommunityTests.tearDown
    login = test_community.CommunityTests.login
    token = test_community.CommunityTests.token
    create = test_community.CommunityTests.create
    picture = staticmethod(test_community.CommunityTests.picture)

    def test_public_privacy_and_only_published_author_posts(self):
        self.manager.update_profile(1, '13700000000', '', '爱猫也爱狗')
        first = self.create().json()
        hidden = self.create().json()
        self.db.moderate(hidden['id'], 1, 'hidden', '测试', 1)
        deleted = self.create().json()
        self.db.delete(deleted['id'], 1)
        second = self.create().json()
        self.client.post('/api/v1/community/posts', headers=self.bob, json={'body':'bob', 'category':'cat','request_key':'00000000-0000-4000-8000-000000000001'})
        data = self.client.get('/api/v1/community/users/1').json()
        self.assertEqual(set(data), {'id','name','bio','avatar_id','post_count','pets'})
        self.assertEqual(data['name'], '宠友_1')
        self.assertEqual(data['post_count'], 2)
        page = self.client.get('/api/v1/community/users/1/posts?limit=1').json()
        self.assertEqual([p['id'] for p in page['items']], [second['id']])
        page = self.client.get(f"/api/v1/community/users/1/posts?before={page['next_cursor']}").json()
        self.assertEqual([p['id'] for p in page['items']], [first['id']])
        self.assertEqual(self.client.get('/api/v1/community/users/999').status_code, 404)
        with self.manager.repository.db:
            self.manager.repository.db.execute('UPDATE users SET disabled=1 WHERE id=1')
        self.assertEqual(self.client.get('/api/v1/community/users/1/posts').status_code, 404)

    def test_avatar_validation_replacement_and_failure(self):
        self.client.app.dependency_overrides[get_avatar_media] = lambda: self.media
        path = '/api/v1/community/me/avatar'
        self.assertEqual(self.client.put(path, content=self.picture()).status_code, 401)
        self.assertEqual(self.client.put(path, headers=self.headers, content=b'<svg/>').status_code, 422)
        self.assertEqual(self.client.put(path, headers=self.headers, content=b'x'*(5*1024*1024+1)).status_code, 413)
        response = self.client.put(path, headers=self.headers, content=self.picture())
        self.assertEqual(response.status_code, 200, response.text)
        first = response.json()['avatar_id']
        url = f'/api/v1/community/users/1/avatar/{first}'
        self.assertEqual(self.client.get(url).headers['content-type'], 'image/webp')
        self.assertEqual(self.client.get('/api/v1/auth/me', headers=self.headers).json()['avatar_id'], first)
        with patch.object(self.media, 'put', side_effect=HTTPException(503, '失败')):
            self.assertEqual(self.client.put(path, headers=self.headers, content=self.picture()).status_code, 503)
        self.assertEqual(self.manager.get_by_id(1)['avatar_id'], first)
        self.assertEqual(self.client.delete(path, headers=self.bob).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        second = self.client.put(path, headers=self.headers, content=self.picture()).json()['avatar_id']
        self.assertNotEqual(first, second)
        self.assertNotIn(first, self.media.items)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.delete(path, headers=self.headers)
        self.assertEqual(self.manager.get_by_id(1)['avatar_id'], '')
        self.assertNotIn(second, self.media.items)
