"""安全接管已存在的 PostgreSQL 库：uv run python -m app.manage_db adopt。"""
import argparse
from app.core.config import Settings
from app.database.migrations import adopt_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['adopt'])
    parser.parse_args()
    heads = adopt_database(Settings().database_url.get_secret_value())
    print('Alembic 当前版本：'+', '.join(heads))


if __name__ == '__main__':
    main()
