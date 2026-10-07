"""Alembic 配置与旧版 PostgreSQL 接管；连接地址不写入 ini 或日志。"""
import importlib.util
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

BACKEND = Path(__file__).resolve().parents[2]
BASELINE = '0001_postgresql'


def sqlalchemy_url(url):
    if not url.startswith(('postgresql://','postgres://','postgresql+psycopg://')):
        raise RuntimeError('请配置 DATABASE_URL 为 PostgreSQL 连接地址')
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    parsed = make_url(url).set(drivername='postgresql+psycopg')
    return parsed if 'connect_timeout' in parsed.query else parsed.update_query_dict({'connect_timeout':'5'})


def alembic_config(connection=None):
    config = Config(str(BACKEND/'alembic.ini'))
    if connection is not None:
        config.attributes['connection'] = connection
    return config


def baseline_metadata():
    # 独立冻结的基线，未来修改目标 metadata 不影响旧库接管验证。
    spec = importlib.util.spec_from_file_location('baichongji_baseline',BACKEND/'alembic'/'baseline_metadata.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.metadata


def upgrade_database(url):
    engine = create_engine(sqlalchemy_url(url),poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(hashtext('baichongji:schema'))")
            tables = set(inspect(connection).get_table_names())
            if 'alembic_version' not in tables and tables:
                raise RuntimeError('现有数据库尚未由 Alembic 管理，请先执行 uv run python -m app.manage_db adopt')
            command.upgrade(alembic_config(connection),'head')
    finally:
        engine.dispose()


def adopt_database(url):
    engine = create_engine(sqlalchemy_url(url),poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(hashtext('baichongji:schema'))")
            context = MigrationContext.configure(connection,opts={'compare_type':True,'compare_server_default':True})
            heads = context.get_current_heads()
            if heads:
                return heads
            expected = baseline_metadata()
            tables = set(inspect(connection).get_table_names())-{'alembic_version'}
            if tables != set(expected.tables):
                raise RuntimeError('现有库与 PostgreSQL 基线表清单不一致，拒绝标记版本；请核对数据库结构')
            differences = compare_metadata(context,expected)
            if differences:
                raise RuntimeError(f'现有库与基线结构不一致，拒绝标记版本：{differences}')
            command.stamp(alembic_config(connection),BASELINE)
            return (BASELINE,)
    finally:
        engine.dispose()
