import unittest
import test_features


class PhoneProfileTests(unittest.TestCase):
    login = test_features.AuthTests.login
    token = test_features.AuthTests.token
    tearDown = test_features.AuthTests.tearDown

    def setUp(self):
        test_features.AuthTests.setUp(self)
        self.phone = '13800138000'

    def register(self, **extra):
        return self.client.post('/api/v1/auth/register', json={'phone': self.phone, 'password': 'secret123', **extra})

    def test_register_login_and_duplicate(self):
        response = self.register(role='admin')
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['phone'], self.phone)
        self.assertEqual(response.json()['role'], 'user')
        self.assertEqual(self.register().status_code, 409)
        login = self.client.post('/api/v1/auth/login', json={'username': self.phone, 'password': 'secret123'})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.manager.login_scope(self.phone), self.manager.login_scope(response.json()['username']))

    def test_validation_and_registration_limit(self):
        for payload in ({'phone': '123'}, {'phone': '1380013800x'}, {'password': '123'}, {'password': '      '}):
            self.assertEqual(self.register(**payload).status_code, 422)
        self.assertEqual(self.register().status_code, 201)
        for _ in range(9):
            self.assertEqual(self.register().status_code, 409)
        response = self.register()
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)

    def test_profile_update_isolation_and_login_compatibility(self):
        token = self.token()
        bob = self.manager.create_user('bob', 'secret123')
        response = self.client.patch('/api/v1/auth/me', headers=token, json={'username': 'alice_new', 'nickname': '猫家长', 'bio': '两只猫', 'id': bob['id'], 'role': 'admin', 'phone': self.phone})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['role'], 'user')
        self.assertIsNone(response.json()['phone'])
        self.assertEqual(self.manager.get_by_id(bob['id'])['username'], 'bob')
        self.assertEqual(self.client.get('/api/v1/auth/me', headers=token).json()['nickname'], '猫家长')
        self.assertIsNotNone(self.manager.authenticate('alice_new', 'secret123'))
        self.assertIsNone(self.manager.authenticate('alice', 'secret123'))
        self.assertEqual(self.client.patch('/api/v1/auth/me', headers=token, json={'username': 'bob'}).status_code, 409)
        self.assertEqual(self.client.patch('/api/v1/auth/me', json={'username': 'stolen'}).status_code, 401)
        self.assertEqual(self.client.patch('/api/v1/auth/me', headers=token, json={'username': 'valid', 'bio': 'x' * 301}).status_code, 422)

    def test_phone_username_conflict(self):
        self.manager.create_user(self.phone, 'secret123')
        self.assertEqual(self.register().status_code, 409)

    def test_different_rate_windows_do_not_reset_each_other(self):
        self.assertEqual(self.limiter.consume_attempt([('hour', 1)], 3600), 0)
        self.assertEqual(self.limiter.consume_attempt([('minute', 1)], 60), 0)
        self.assertGreater(self.limiter.consume_attempt([('hour', 1)], 3600), 0)
