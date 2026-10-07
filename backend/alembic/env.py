from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool
from app.core.config import Settings
from app.database.metadata import metadata
from app.database.migrations import sqlalchemy_url

config = context.config
if config.config_file_name and config.attributes.get('connection') is None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = metadata


def configure(connection=None, url=None):
    context.configure(connection=connection, url=url, target_metadata=target_metadata,
        compare_type=True, compare_server_default=True,
        literal_binds=context.is_offline_mode(), dialect_opts={'paramstyle':'named'})


def run_online(connection):
    configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    url = sqlalchemy_url(config.attributes.get('database_url') or Settings().database_url.get_secret_value())
    configure(url=url)
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get('connection') is not None:
    run_online(config.attributes['connection'])
else:
    url = sqlalchemy_url(config.attributes.get('database_url') or Settings().database_url.get_secret_value())
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(hashtext('baichongji:schema'))")
            run_online(connection)
    finally:
        engine.dispose()
