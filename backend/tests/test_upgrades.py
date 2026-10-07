import os
import unittest
from unittest.mock import patch
from uuid import uuid4
from app.api.v1 import governance,ai_feedback
import test_community
import test_postgres


class GovernanceTests(unittest.TestCase):
    setUp=test_community.CommunityTests.setUp
    tearDown=test_community.CommunityTests.tearDown
    login=test_community.CommunityTests.login
    token=test_community.CommunityTests.token
    create=test_community.CommunityTests.create

    def setup_routes(self):
        self.client.app.include_router(governance.router,prefix='/api/v1')
        self.client.app.include_router(ai_feedback.router,prefix='/api/v1')

    def test_profile_governance_conflict_public_privacy_and_owner_audit(self):
        self.setup_routes()
        self.manager.update_profile(1,'alice','公开昵称','不合适的简介')
        url='/api/v1/admin/users/1/moderation'
        body={'hidden':True,'reason':'资料需要修改','version':2,'field':'profile'}
        self.assertEqual(self.client.patch(url,headers=self.headers,json=body).status_code,403)
        self.manager.set_role('bob','admin')
        self.assertEqual(self.client.patch(url,headers=self.bob,json=body).status_code,200)
        self.assertEqual(self.client.patch(url,headers=self.bob,json=body).status_code,409)
        public=self.client.get('/api/v1/community/users/1').json()
        self.assertEqual(public['name'],'宠友_1');self.assertEqual(public['bio'],'')
        self.manager.update_profile(1,'alice','新昵称','修改后的简介')
        self.assertEqual(self.client.get('/api/v1/community/users/1').json()['bio'],'')
        events=self.client.get('/api/v1/community/me/moderation?kind=users',headers=self.headers).json()['items']
        self.assertEqual(events[0]['reason'],'资料需要修改')
        self.assertNotIn('before_state',events[0]);self.assertNotIn('actor_id',events[0])
        self.assertEqual(self.client.get('/api/v1/community/me/moderation?kind=users',headers=self.bob).json()['items'],[])
        audit=self.client.get('/api/v1/admin/governance?kind=users',headers=self.bob).json()['items'][0]
        self.assertEqual(audit['before_state']['bio'],'不合适的简介')
        self.assertTrue(audit['after_state']['profile_hidden'])
        self.assertNotIn('password_hash',str(audit))
        body.update(hidden=False,version=4,reason='复核通过')
        self.assertEqual(self.client.patch(url,headers=self.bob,json=body).status_code,200)
        self.assertEqual(self.client.get('/api/v1/community/users/1').json()['name'],'新昵称')

    def test_pet_governance_visibility_metrics_and_rollback(self):
        self.setup_routes();self.manager.set_role('bob','admin')
        values=dict(name='小猫',species='cat',breed='',sex='unknown',birthday=None,bio='',photo_id='')
        pet=self.db.write_pet(1,values,request_key=str(uuid4()))
        post=self.create(pet_ids=[pet['id']]).json()
        body=dict(hidden=True,reason='档案有不当内容',version=pet['version'])
        path=f'/api/v1/admin/pets/{pet["id"]}/moderation'
        self.assertEqual(self.client.patch(path,headers=self.bob,json=body).status_code,200)
        self.assertEqual(self.client.get(f'/api/v1/community/pets/{pet["id"]}').status_code,404)
        self.assertEqual(self.client.get(f'/api/v1/community/posts/{post["id"]}').json()['pets'],[])
        self.assertTrue(self.client.get('/api/v1/community/me/pets',headers=self.headers).json()['items'][0]['hidden'])
        self.assertEqual(self.client.get('/api/v1/admin/community-metrics',headers=self.bob).json()['hidden_pets'],1)
        self.db.write_pet(1,{**values,'name':'新名字'},pet_id=pet['id'],version=2)
        self.assertEqual(self.client.get(f'/api/v1/community/pets/{pet["id"]}').status_code,404)
        body.update(hidden=False,version=3)
        with patch('app.database.repositories.governance.GovernanceRepository.add',side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):self.db.moderate_pet(pet['id'],2,False,'恢复',3)
        self.assertTrue(self.db.admin_pet(pet['id'])['hidden'])
        self.assertEqual(self.client.patch(path,headers=self.bob,json=body).status_code,200)
        self.assertEqual(self.client.get(f'/api/v1/community/pets/{pet["id"]}').status_code,200)

    def test_ai_feedback_isolation_sources_context_and_read_without_recovery(self):
        self.setup_routes()
        store=self.service.turn_store;rid=str(uuid4())
        store.begin('1','chat',rid,'问题',None,{'id':1,'name':'猫'})
        store.sources('1',rid,[{'source':'知识资料','id':'doc','excerpt':'片段'}])
        store.finish('1',rid,'completed','回答')
        url=f'/api/v1/chat/requests/{rid}/feedback'
        self.assertEqual(self.client.put(url,headers=self.bob,json={'value':'helpful'}).status_code,404)
        self.assertEqual(self.client.put(url,headers=self.headers,json={'value':'helpful'}).status_code,200)
        messages=store.messages('1','chat')
        self.assertEqual(messages[-1]['sources'][0]['source'],'知识资料')
        self.assertEqual(messages[-1]['feedback'],'helpful')
        self.assertEqual(messages[0]['context']['id'],1)
        other=str(uuid4());store.begin('1','chat',other,'正在生成',None)
        from app.services.ai.turns import TurnService
        reader=TurnService(repository=None,path=store.repository.db_path if hasattr(store.repository,'db_path') else str(self.temp.name)+'/pet.db',recover=False)
        reader.close()
        self.assertEqual(store.get('1',other)['status'],'running')
        self.assertEqual(self.client.get('/api/v1/chat/threads',headers=self.headers).status_code,200) if hasattr(self.service,'list_threads') else None

    def test_pet_context_ownership_and_ai_post_label_cannot_be_removed_by_edit(self):
        values=dict(name='奶糖',species='cat',breed='',sex='unknown',birthday=None,bio='背景资料',photo_id='')
        other=self.db.write_pet(2,values,request_key=str(uuid4()))
        request=dict(message='养护问题',image_url='',thread_id='pet-chat',request_id=str(uuid4()),pet_id=other['id'])
        self.assertEqual(self.client.post('/api/v1/chat/stream',headers=self.headers,json=request).status_code,404)
        own=self.db.write_pet(1,values,request_key=str(uuid4()))
        request.update(pet_id=own['id'],request_id=str(uuid4()))
        response=self.client.post('/api/v1/chat/stream',headers=self.headers,json=request)
        self.assertEqual(response.status_code,200)
        self.assertIn('completed',response.text)
        self.assertIn('奶糖',self.service.turn_store.get('1',request['request_id'])['context'])
        self.assertEqual(self.db.listing()['items'],[])
        post=self.create(ai_generated=True).json()
        self.assertTrue(post['ai_generated'])
        values=dict(title='修改',body='已核实的日常',category='cat',tags=[],images=[],ai_generated=False)
        self.db.write(1,values,post_id=post['id'],version=post['version'])
        self.assertTrue(self.db.get(post['id'])['ai_generated'])


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='1','Real PostgreSQL required')
class PostgresUpgradeTests(test_postgres.SchemaTest):
    setUp=test_postgres.PostgresApiTests.setUp
    tearDown=test_community.CommunityTests.tearDown
    login=test_community.CommunityTests.login
    token=test_community.CommunityTests.token
    create=test_community.CommunityTests.create
    setup_routes=GovernanceTests.setup_routes
    test_profiles=GovernanceTests.test_profile_governance_conflict_public_privacy_and_owner_audit
    test_pets=GovernanceTests.test_pet_governance_visibility_metrics_and_rollback
    test_ai_context=GovernanceTests.test_pet_context_ownership_and_ai_post_label_cannot_be_removed_by_edit

    def test_public_search_and_history_never_recovers_running(self):
        self.manager.update_profile(1,'alice','猫咪家长','简介')
        self.assertEqual(self.client.get('/api/v1/community/search/users?q=猫咪').json()['items'][0]['name'],'猫咪家长')
        self.assertEqual(self.client.get('/api/v1/community/search/users?q=13771900205').json()['items'],[])
        pet=self.db.write_pet(1,dict(name='奶糖',species='cat',breed='英短',sex='unknown',birthday=None,bio='',photo_id=''),request_key=str(uuid4()))
        self.assertEqual(self.client.get('/api/v1/community/search/pets?q=英短').json()['items'][0]['id'],pet['id'])
        self.db.moderate_pet(pet['id'],2,True,'隐藏',1)
        self.assertEqual(self.client.get('/api/v1/community/search/pets?q=英短').json()['items'],[])
        rid=str(uuid4());self.service.turn_store.begin('1','ongoing',rid,'问题',None)
        from app.services.ai.history import ConversationHistory
        reader=ConversationHistory(self.url);self.addCleanup(reader.close)
        self.client.app.state.chat_history=reader
        self.client.app.state.pet_agent_service=None
        self.client.app.state.initialize_ai=lambda: (_ for _ in ()).throw(AssertionError('Must not initialize model'))
        self.assertEqual(self.client.get('/api/v1/chat/messages?thread_id=ongoing',headers=self.headers).status_code,200)
        self.assertEqual(self.service.turn_store.get('1',rid)['status'],'running')

    def test_durable_knowledge_job_failure_retry_and_source_replacement(self):
        from types import SimpleNamespace
        from threading import RLock
        from app.services.ai.knowledge_jobs import KnowledgeJobs
        from app.core.errors import BusinessError
        jobs=KnowledgeJobs(self.url);self.addCleanup(jobs.close)
        class FakeIndex:
            lock=RLock()
            def get(self,**kwargs):return {'documents':['保留其他来源'],'metadatas':[{'source':'other'}]}
        rag=SimpleNamespace(repository=FakeIndex())
        job=jobs.create(1,'宠物养护','这是导入源文本')
        rag.rebuild_documents=lambda *args: (_ for _ in ()).throw(RuntimeError('provider secret'))
        with self.assertRaises(BusinessError):jobs.run(job['id'],rag)
        row=jobs.listing()['items'][0]
        self.assertEqual(row['status'],'failed');self.assertNotIn('provider secret',row['error'])
        captured=[]
        def build(docs,metas,docs_hash,**kwargs):captured.extend(docs);return 'new-version'
        rag.rebuild_documents=build
        self.assertEqual(jobs.run(job['id'],rag)['status'],'completed')
        self.assertIn('保留其他来源',captured);self.assertIn('这是导入源文本',captured)
        self.assertEqual(jobs.run(job['id'],rag)['version'],'new-version')
        self.assertEqual(len(captured),2)
        # Chroma may publish successfully immediately before the SQL completion write fails.
        interrupted=jobs.create(1,'中断的任务','已被索引的源文本')
        rag.repository.metadata={'build_id':interrupted['id']}
        rag.repository.version_list=lambda:{'active':'already-published'}
        rag.rebuild_documents=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('Must not embed twice'))
        self.assertEqual(jobs.run(interrupted['id'],rag)['version'],'already-published')
