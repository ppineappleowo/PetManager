import sqlite3
import unittest
from unittest.mock import patch
from contextlib import closing
from pathlib import Path
from uuid import uuid4
from app.services.community.posts import CommunityService
from app.database.redis import RedisUnavailable
import test_community


class PetTests(unittest.TestCase):
    setUp = test_community.CommunityTests.setUp
    tearDown = test_community.CommunityTests.tearDown
    login = test_community.CommunityTests.login
    token = test_community.CommunityTests.token
    create = test_community.CommunityTests.create
    upload = test_community.CommunityTests.upload
    picture = staticmethod(test_community.CommunityTests.picture)

    def add_pet(self, headers=None, **values):
        return self.client.post('/api/v1/community/me/pets',headers=headers or self.headers,json={'name':'团子','species':'cat','request_key':str(uuid4()),**values})

    def test_validation_auth_idempotency_and_edit_conflict(self):
        path = '/api/v1/community/me/pets'
        self.assertEqual(self.client.get(path).status_code,401)
        self.assertEqual(self.client.post(path,json={}).status_code,401)
        for values in ({'name':' '},{'name':'x'*33},{'species':'general'},{'birthday':'2999-01-01'},{'birthday':'2023-02-30'},{'photo_id':'../x'}):
            self.assertEqual(self.add_pet(**values).status_code,422)
        key = str(uuid4())
        pet = self.add_pet(request_key=key,birthday='2020-01-01').json()
        self.assertEqual(self.add_pet(request_key=key,birthday='2020-01-01').json()['id'],pet['id'])
        self.assertEqual(self.add_pet(request_key=key,name='新名字').status_code,409)
        url = f"{path}/{pet['id']}"
        edit = {'name':'饭团','species':'dog','version':pet['version']}
        self.assertEqual(self.client.put(url,headers=self.bob,json=edit).status_code,404)
        self.assertEqual(self.client.put(url,headers=self.headers,json=edit).json()['name'],'饭团')
        self.assertEqual(self.client.put(url,headers=self.headers,json=edit).status_code,409)
        self.assertEqual(self.client.delete(url+'?version=1',headers=self.headers).status_code,409)
        self.assertEqual(len(self.client.get(path,headers=self.headers).json()['items']),1)

    def test_photo_ownership_cleanup_and_public_visibility(self):
        photo = self.upload()
        self.assertEqual(self.add_pet(headers=self.bob,photo_id=photo).status_code,422)
        pet = self.add_pet(photo_id=photo).json()
        url = f"/api/v1/community/pets/{pet['id']}"
        data = self.client.get(url).json()
        self.assertNotIn('user_id',data)
        self.assertNotIn('phone',str(data))
        image_url = f'{url}/photo/{photo}'
        self.assertEqual(self.client.get(image_url).status_code,200)
        self.assertEqual(self.client.get(url+'/photo/'+'a'*32).status_code,404)
        with self.db.repository.db:
            self.db.repository.db.execute("UPDATE media SET touched_at=datetime('now','-2 days')")
        self.assertEqual(self.db.clean_media(self.media),0)
        self.assertIn(photo,self.media.items)
        self.client.delete(f"/api/v1/community/me/pets/{pet['id']}?version=1",headers=self.headers)
        self.assertEqual(self.client.get(image_url).status_code,404)
        with self.db.repository.db:
            self.db.repository.db.execute("UPDATE media SET touched_at=datetime('now','-2 days')")
        self.assertEqual(self.db.clean_media(self.media),1)

    def test_post_links_filter_pagination_and_delete_preserves_posts(self):
        pet = self.add_pet().json()
        other = self.add_pet(headers=self.bob).json()
        self.assertEqual(self.create(pet_ids=[other['id']]).status_code,404)
        self.assertEqual(self.create(pet_ids=[pet['id'],pet['id']]).status_code,422)
        self.assertEqual(self.create(pet_ids=list(range(1,7))).status_code,422)
        first = self.create(pet_ids=[pet['id']]).json()
        second = self.create(pet_ids=[pet['id']]).json()
        hidden = self.create(pet_ids=[pet['id']]).json()
        self.db.moderate(hidden['id'],1,'hidden','测试',1)
        url=f"/api/v1/community/pets/{pet['id']}"
        self.assertEqual(self.client.get(url).json()['post_count'],2)
        page=self.client.get(url+'/posts?limit=1').json()
        self.assertEqual(page['items'][0]['id'],second['id'])
        page=self.client.get(url+f"/posts?before={page['next_cursor']}").json()
        self.assertEqual([p['id'] for p in page['items']],[first['id']])
        user=self.client.get('/api/v1/community/users/1').json()
        self.assertEqual([p['id'] for p in user['pets']],[pet['id']])
        self.assertEqual(self.client.delete(f"/api/v1/community/me/pets/{pet['id']}?version=1",headers=self.bob).status_code,404)
        self.client.delete(f"/api/v1/community/me/pets/{pet['id']}?version=1",headers=self.headers)
        post=self.client.get(f"/api/v1/community/posts/{first['id']}").json()
        self.assertEqual(post['body'],first['body'])
        self.assertEqual(post['pets'],[])
        self.assertEqual(post['version'],2)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.create(pet_ids=[pet['id']]).status_code,404)

    def test_edit_links_disabled_user_and_redis_outage(self):
        pet=self.add_pet().json()
        with patch.object(self.limiter,'consume_attempt',side_effect=RedisUnavailable('private')):
            self.assertEqual(self.add_pet().status_code,503)
            self.assertEqual(self.client.get(f"/api/v1/community/pets/{pet['id']}").status_code,200)
            self.assertEqual(self.login().status_code,200)
        post=self.create().json()
        url=f"/api/v1/community/posts/{post['id']}"
        result=self.client.put(url,headers=self.headers,json={'body':'新日常','category':'cat','pet_ids':[pet['id']],'version':1})
        self.assertEqual(result.json()['pet_ids'],[pet['id']])
        result=self.client.put(url,headers=self.headers,json={'body':'新日常','category':'cat','pet_ids':[],'version':2})
        self.assertEqual(result.json()['pet_ids'],[])
        with self.manager.repository.db:
            self.manager.repository.db.execute('UPDATE users SET disabled=1 WHERE id=1')
        self.assertEqual(self.client.get(f"/api/v1/community/pets/{pet['id']}").status_code,404)
        self.assertEqual(self.add_pet().status_code,401)

    def test_v3_migration_backup_and_reopen(self):
        post=self.create().json()
        with self.db.repository.db:
            self.db.repository.db.executescript('DROP TABLE post_pets; DROP TABLE pets; DELETE FROM community_migrations WHERE version=3;')
        before=set((Path(self.temp.name)/'backups').glob('community-before-v3-*.db'))
        self.db.close()
        path=Path(self.temp.name)/'community.db'
        self.db=CommunityService(path)
        self.client.app.state.community_store=self.db
        backups=set((path.parent/'backups').glob('community-before-v3-*.db'))-before
        self.assertEqual(len(backups),1)
        with closing(sqlite3.connect(backups.pop())) as backup:
            self.assertEqual(backup.execute('SELECT id FROM posts').fetchone()[0],post['id'])
            self.assertIsNone(backup.execute('SELECT 1 FROM community_migrations WHERE version=3').fetchone())
        self.assertEqual(self.client.get(f"/api/v1/community/posts/{post['id']}").json()['pet_ids'],[])
        self.assertEqual(self.add_pet().status_code,201)
