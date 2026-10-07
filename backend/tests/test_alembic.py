"""真实 PostgreSQL 隔离 schema：迁移、接管、漂移检测和后续 autogenerate。"""
import io
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.database.migrations import BACKEND, BASELINE, alembic_config, adopt_database, sqlalchemy_url, upgrade_database
from app.database.metadata import metadata
import test_postgres


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='1','Set RUN_POSTGRES_TESTS=1 for real PostgreSQL')
class AlembicTests(test_postgres.SchemaTest):
    def setUp(self):
        self.setup_schema()
        self.engine=sa.create_engine(sqlalchemy_url(self.url))
        self.head=ScriptDirectory.from_config(alembic_config()).get_current_head()
        self.addCleanup(self.engine.dispose)

    def test_fresh_schema_matches_metadata_and_roundtrip(self):
        with self.engine.begin() as connection:
            config=alembic_config(connection)
            self.assertEqual(MigrationContext.configure(connection).get_current_heads(),(self.head,))
            command.check(config)
            self.assertEqual(compare_metadata(MigrationContext.configure(connection,opts={'compare_server_default':True}),metadata),[])
            command.downgrade(config,'base')
            self.assertEqual(set(sa.inspect(connection).get_table_names()),{'alembic_version'})
            command.upgrade(config,'head')
            command.check(config)

    def test_adopt_preserves_rows_and_is_repeatable(self):
        with self.engine.begin() as connection:
            command.downgrade(alembic_config(connection), BASELINE)
            connection.exec_driver_sql('DROP TABLE alembic_version')
            connection.execute(sa.text("INSERT INTO users(username,password_hash) VALUES ('preserved','test-hash')"))
        with self.assertRaisesRegex(RuntimeError,'manage_db adopt'):
            upgrade_database(self.url)
        self.assertEqual(adopt_database(self.url),(BASELINE,))
        self.assertEqual(adopt_database(self.url),(BASELINE,))
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql('SELECT username,password_hash FROM users').one(),('preserved','test-hash'))

    def test_adopt_rejects_drift_without_stamp(self):
        with self.engine.begin() as connection:
            command.downgrade(alembic_config(connection), BASELINE)
            connection.exec_driver_sql('DROP TABLE alembic_version')
            connection.exec_driver_sql('DROP INDEX users_phone')
        with self.assertRaisesRegex(RuntimeError,'基线结构不一致'):
            adopt_database(self.url)
        with self.engine.connect() as connection:
            self.assertNotIn('alembic_version',sa.inspect(connection).get_table_names())

    def test_offline_sql_contains_schema_not_credentials(self):
        output=io.StringIO()
        config=alembic_config()
        config.output_buffer=output
        config.attributes['database_url']=self.url
        command.upgrade(config,'head',sql=True)
        result=output.getvalue()
        self.assertIn('CREATE TABLE users',result)
        self.assertIn('alembic_version',result)
        self.assertNotIn(self.url,result)

    def test_future_autogenerate_upgrade_and_downgrade(self):
        proposed=sa.MetaData()
        for table in metadata.sorted_tables:
            table.to_metadata(proposed)
        proposed.tables['users'].append_column(sa.Column('test_profile_note',sa.Text(),nullable=True))
        with tempfile.TemporaryDirectory() as temporary:
            scripts=Path(temporary)/'alembic'
            shutil.copytree(BACKEND/'alembic',scripts,ignore=shutil.ignore_patterns('__pycache__'))
            with self.engine.begin() as connection:
                config=alembic_config(connection)
                config.set_main_option('script_location',str(scripts).replace('%','%%'))
                with patch('app.database.metadata.metadata',proposed):
                    revision=command.revision(config,message='test add profile note',autogenerate=True)
                    self.assertIn('add_column',Path(revision.path).read_text(encoding='utf-8'))
                    command.upgrade(config,'head')
                    self.assertIn('test_profile_note',{column['name'] for column in sa.inspect(connection).get_columns('users')})
                    command.check(config)
                    command.downgrade(config,self.head)
                self.assertEqual(compare_metadata(MigrationContext.configure(connection,opts={'compare_server_default':True}),metadata),[])
