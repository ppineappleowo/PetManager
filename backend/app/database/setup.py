"""保留初始化入口，所有建表/升级统一交给 Alembic。"""
from app.database.migrations import upgrade_database


def initialize_database(url):
    upgrade_database(url)
