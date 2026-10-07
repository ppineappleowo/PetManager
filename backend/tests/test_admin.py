import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from app.api.v1 import admin
import test_features


class AdminTests(unittest.TestCase):
    login = test_features.AuthTests.login
    token = test_features.AuthTests.token
    tearDown = test_features.AuthTests.tearDown

    def setUp(self):
        test_features.AuthTests.setUp(self)
        self.client.app.include_router(admin.router, prefix='/api/v1')
        self.service.list_threads = lambda uid: [{'thread_id': t, 'title': '测试会话', 'message_count': len(self.service.turn_store.messages(uid, t))} for t in self.service.turn_store.thread_ids(uid)]
        self.service.get_messages = lambda tid, uid: self.service.turn_store.messages(uid, tid)
        self.service.clear_messages = lambda tid, uid: self.service.turn_store.delete(uid, tid)
        self.collection = Mock()
        self.collection.count.return_value = 1
        self.collection.get.return_value = {'ids': ['doc1'], 'documents': ['知识正文'], 'metadatas': [{'source': 'manual'}]}
        from app.services.ai.retrieval import RAGManager
        self.service.rag_manager = RAGManager.__new__(RAGManager)
        self.service.rag_manager.repository = self.collection

    def admin_token(self):
        self.manager.set_role('alice', 'admin')
        return self.token()

    def test_all_routes_require_admin(self):
        routes = [('GET', '/overview', None), ('GET', '/users', None), ('GET', '/threads', None),
                  ('GET', '/knowledge', None), ('POST', '/knowledge', {'text': '知识'}),
                  ('DELETE', '/knowledge/doc1', None), ('PATCH', '/users/1', {'role': 'admin'}),
                  ('GET', '/users/1/messages?thread_id=x', None), ('DELETE', '/users/1/messages?thread_id=x', None),
                  ('POST', '/users/1/stop?thread_id=x', None)]
        token = self.token()
        for method, path, body in routes:
            self.assertEqual(self.client.request(method, '/api/v1/admin' + path, json=body).status_code, 401)
            self.assertEqual(self.client.request(method, '/api/v1/admin' + path, json=body, headers=token).status_code, 403)

    def test_user_controls_and_token_revocation(self):
        token = self.admin_token()
        bob = self.manager.create_user('bob', 'secret123')
        bob_token = self.client.post('/api/v1/auth/login', json={'username': 'bob', 'password': 'secret123'}).json()['access_token']
        path = f"/api/v1/admin/users/{bob['id']}"
        self.assertEqual(self.client.patch(path, headers=token, json={'disabled': True}).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + bob_token}).status_code, 401)
        self.assertIsNone(self.manager.authenticate('bob', 'secret123'))
        self.assertEqual(self.client.patch(path, headers=token, json={'disabled': False, 'role': 'admin'}).status_code, 200)
        self.assertIsNotNone(self.manager.authenticate('bob', 'secret123'))
        self.assertEqual(self.client.patch('/api/v1/admin/users/1', headers=token, json={'role': 'user'}).status_code, 409)
        self.assertEqual(self.client.patch('/api/v1/admin/users/1', headers=token, json={'disabled': True}).status_code, 409)
        self.assertEqual(self.client.patch(path, headers=token, json={'role': 'root'}).status_code, 422)
        self.assertEqual(self.client.patch('/api/v1/admin/users/999', headers=token, json={'revoke': True}).status_code, 404)
        self.assertEqual(self.client.patch('/api/v1/admin/users/1', headers=token, json={'revoke': True}).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/admin/users', headers=token).status_code, 401)

    def test_overview_search_pagination_no_secrets(self):
        token = self.admin_token()
        self.manager.create_user('bob', 'secret123')
        response = self.client.get('/api/v1/admin/overview', headers=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['users'], 2)
        self.assertNotIn('jwt_secret_key', response.text)
        response = self.client.get('/api/v1/admin/users?q=bob&limit=1', headers=token)
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(response.json()['items'][0]['username'], 'bob')
        self.assertNotIn('password_hash', response.text)
        self.assertNotIn('token_version', response.text)
        self.assertEqual(self.client.get('/api/v1/admin/users?limit=1000', headers=token).status_code, 422)

    def test_thread_isolation_and_delete(self):
        token = self.admin_token()
        self.manager.create_user('bob', 'secret123')
        for uid in ('1', '2'):
            rid = str(uuid4())
            self.service.turn_store.begin(uid, 'same', rid, '问题', '')
            self.service.turn_store.finish(uid, rid, 'completed', '答案')
        self.assertEqual(self.client.get('/api/v1/admin/threads', headers=token).json()['total'], 2)
        path = '/api/v1/admin/users/2/messages?thread_id=same'
        self.assertEqual(len(self.client.get(path, headers=token).json()['messages']), 2)
        self.assertEqual(self.client.delete(path, headers=token).status_code, 200)
        self.assertEqual(len(self.service.turn_store.messages('1', 'same')), 2)
        self.assertEqual(self.service.turn_store.messages('2', 'same'), [])

    def test_knowledge_operations(self):
        token = self.admin_token()
        response = self.client.get('/api/v1/admin/knowledge?offset=0&limit=20', headers=token)
        self.assertEqual(response.json()['items'][0]['text'], '知识正文')
        self.assertEqual(self.client.post('/api/v1/admin/knowledge', headers=token, json={'text': '  '}).status_code, 422)
        self.assertEqual(self.client.post('/api/v1/admin/knowledge', headers=token, json={'text': '新知识'}).json()['added'], 1)
        self.assertEqual(self.client.delete('/api/v1/admin/knowledge/doc1', headers=token).status_code, 200)
        self.collection.delete.assert_called_once_with(ids=['doc1'])
        self.collection.get.return_value = {'ids': []}
        self.assertEqual(self.client.delete('/api/v1/admin/knowledge/missing', headers=token).status_code, 404)
