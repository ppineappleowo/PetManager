"""RUN_POSTGRES_TESTS=1 启用；每个测试使用独立临时 schema，不写业务表。"""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4
from unittest.mock import patch
import psycopg
from psycopg import sql
from app.setup_local_services import local_database_url
from app.database.setup import initialize_database
from app.database.postgres import PostgresDatabase
from app.services.users import UserService
from app.services.community.posts import CommunityService
from app.services.ai.turns import TurnService
from app.migrate_postgres import migrate
import test_features
import test_community
import test_interactions
import test_pets
import test_public_profiles
import test_bookmarks as bookmarks_tests
import test_notifications as notifications_tests
import test_report_feedback as report_feedback_tests


class SchemaTest(unittest.TestCase):
    def setup_schema(self):
        self.base_url=os.getenv('TEST_DATABASE_URL') or local_database_url()
        self.schema='test_'+uuid4().hex
        with psycopg.connect(self.base_url,autocommit=True) as connection:
            connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.url=self.base_url+('&' if '?' in self.base_url else '?')+urlencode({'options':'-csearch_path='+self.schema})
        self.addCleanup(self.drop_schema)
        initialize_database(self.url)

    def drop_schema(self):
        # 仅删除本测试随机生成的隔离 schema。
        if not self.schema.startswith('test_') or len(self.schema)!=37:
            raise RuntimeError('Invalid test schema')
        with psycopg.connect(self.base_url,autocommit=True) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='1','Set RUN_POSTGRES_TESTS=1 for real PostgreSQL')
class PostgresApiTests(SchemaTest):
    def setUp(self):
        self.setup_schema()
        with patch.object(test_features,'UserService',side_effect=lambda path:UserService(self.url)), \
             patch.object(test_features,'TurnService',side_effect=lambda path:TurnService(self.url)), \
             patch.object(test_community,'CommunityService',side_effect=lambda path:CommunityService(self.url)):
            test_community.CommunityTests.setUp(self)

    tearDown=test_community.CommunityTests.tearDown
    login=test_features.AuthTests.login
    token=test_features.AuthTests.token
    create=test_community.CommunityTests.create
    upload=test_community.CommunityTests.upload
    picture=staticmethod(test_community.CommunityTests.picture)
    comment=test_interactions.InteractionTests.comment
    add_pet=test_pets.PetTests.add_pet
    test_login=test_features.AuthTests.test_login_uses_database_without_rate_limiter
    test_password=test_features.AuthTests.test_password_change_revokes_old_token
    test_public_feed=test_community.CommunityTests.test_public_feed_privacy_pagination_and_ownership
    test_media=test_community.CommunityTests.test_images_validation_ownership_and_limit
    test_moderation=test_community.CommunityTests.test_moderation_edit_cannot_republish_and_delete_cannot_restore
    test_cleanup=test_community.CommunityTests.test_cleanup_preserves_referenced_and_recent_media
    test_comments=test_interactions.InteractionTests.test_comment_reply_retry_privacy_delete_and_pagination
    test_reports=test_interactions.InteractionTests.test_report_permissions_dedup_snapshot_resolution_and_deleted_target
    test_likes=test_interactions.InteractionTests.test_like_idempotence_concurrency_and_counts
    test_pet_validation=test_pets.PetTests.test_validation_auth_idempotency_and_edit_conflict
    test_pet_photos=test_pets.PetTests.test_photo_ownership_cleanup_and_public_visibility
    test_pet_links=test_pets.PetTests.test_post_links_filter_pagination_and_delete_preserves_posts
    test_pet_edit=test_pets.PetTests.test_edit_links_disabled_user_and_redis_outage
    test_profile=test_public_profiles.PublicProfilesTests.test_public_privacy_and_only_published_author_posts
    test_avatar=test_public_profiles.PublicProfilesTests.test_avatar_validation_replacement_and_failure
    test_bookmarks=bookmarks_tests.BookmarkTests.test_bookmark_privacy_order_and_retry
    test_bookmark_visibility=bookmarks_tests.BookmarkTests.test_hidden_deleted_and_concurrent_bookmarks
    test_notifications=notifications_tests.NotificationTests.test_recipients_retry_privacy_and_read_boundary
    test_notification_rollback=notifications_tests.NotificationTests.test_notification_failure_rolls_back_comment_and_visibility
    test_report_feedback=report_feedback_tests.ReportFeedbackTests.test_report_feedback_ownership_filters_and_pagination
    test_report_feedback_visibility=report_feedback_tests.ReportFeedbackTests.test_report_feedback_hidden_deleted_and_restored_targets
    test_report_feedback_rollback=report_feedback_tests.ReportFeedbackTests.test_report_resolution_failure_rolls_back_feedback_content_and_audit

    def test_turns_persistence_and_retry(self):
        store=self.service.turn_store
        row=store.begin('1','thread','req','问题',None)
        self.assertEqual(row['status'],'running')
        store.finish('1','req','completed','回答')
        reopened=TurnService(self.url)
        try:
            self.assertEqual(reopened.messages('1','thread')[-1]['content'],'回答')
            self.assertEqual(reopened.messages('2','thread'),[])
            self.assertEqual(reopened.begin('1','thread','req','问题',None)['status'],'completed')
        finally:
            reopened.close()

    def test_rollback_duplicate_and_cross_connection_like(self):
        from concurrent.futures import ThreadPoolExecutor
        other=CommunityService(self.url)
        self.addCleanup(other.close)
        post=self.create().json()['id']
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda i:(self.db if i%2 else other).like(post,1,True),range(12)))
        self.assertEqual(self.db.interaction_counts(post)['like_count'],1)
        self.assertIsNone(self.manager.create_user('alice','secret123'))
        self.assertIsNotNone(self.manager.get_by_id(1))
        with self.assertRaises(RuntimeError):
            with self.manager.repository.db:
                self.manager.repository.db.execute("UPDATE users SET nickname='rollback' WHERE id=1")
                raise RuntimeError('rollback')
        self.assertEqual(self.manager.get_by_id(1)['nickname'],'')


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='1','Set RUN_POSTGRES_TESTS=1 for real PostgreSQL')
class PostgresMigrationTests(SchemaTest):
    def setUp(self):
        self.setup_schema()

    def test_import_backup_legacy_history_and_idempotency(self):
        from langchain.messages import HumanMessage,AIMessage
        from langgraph.checkpoint.sqlite import SqliteSaver
        from app.database.legacy.history import LegacyHistory
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            users=UserService(str(root/'users.db'))
            users.create_user('legacy','secret123')
            old_hash=users.repository.db.execute('SELECT password_hash FROM users').fetchone()[0]
            users.close()
            community=CommunityService(root/'community.db')
            post=community.write(1, dict(title='',body='收藏迁移',category='cat',tags=[],images=[]),request_key=str(uuid4()))
            community.bookmarks.set(1,post['id'],True)
            community.close()
            turns=TurnService(root/'pet.db')
            turns.begin('1','chat','request','现在的问题',None)
            turns.finish('1','request','completed','现在的答案');turns.close()
            with closing(sqlite3.connect(root/'pet.db')) as connection:
                saver=SqliteSaver(connection);saver.setup()
                kind,data=saver.serde.dumps_typed({'channel_values':{'messages':[HumanMessage(content='旧问题'),AIMessage(content='旧答案')]}})
                connection.execute('INSERT INTO checkpoints(thread_id,checkpoint_ns,checkpoint_id,type,checkpoint) VALUES(?,?,?,?,?)',('chat','user:1','legacy-id',kind,data));connection.commit()
            report=migrate(root,self.url)
            self.assertEqual(report['tables']['users']['rows'],1)
            self.assertEqual(report['tables']['post_bookmarks']['rows'],1)
            self.assertTrue((Path(report['backup_directory'])/'users.db').exists())
            self.assertTrue(migrate(root,self.url)['already_imported'])
            new_users=UserService(self.url)
            try:
                self.assertEqual(new_users.repository.db.execute('SELECT password_hash FROM users').fetchone()[0],old_hash)
                self.assertIsNotNone(new_users.authenticate('legacy','secret123'))
                self.assertEqual(new_users.create_user('newuser','secret123')['id'],2)
            finally:
                new_users.close()
            database=PostgresDatabase(self.url,'turns')
            try:
                history=LegacyHistory(database).get({'configurable':{'thread_id':'chat','checkpoint_ns':'user:1'}})
                self.assertEqual(history['channel_values']['messages'][1].content,'旧答案')
                self.assertEqual(database.execute('SELECT answer FROM chat_turns').fetchone()[0],'现在的答案')
            finally:
                database.close()
            # 修改源库后重跑不得覆盖目标已有新账号。
            users=UserService(str(root/'users.db'));users.create_user('changed','secret123');users.close()
            with self.assertRaises(RuntimeError):
                migrate(root,self.url)
