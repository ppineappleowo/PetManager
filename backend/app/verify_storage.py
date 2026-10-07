"""验证当前应用数据库和 Redis，并检查旧会话能反序列化；不输出账号或内容。"""
from fastapi.testclient import TestClient
from app.main import app
from app.database.repositories.history import HistoryRepository


def main():
    with TestClient(app) as client:
        for path in ('/health/database','/health/redis','/api/v1/community/posts'):
            response=client.get(path)
            response.raise_for_status()
            print(f'{path}: {response.status_code}')
        database=HistoryRepository(app.state.settings.database_url.get_secret_value())
        try:
            count = database.verify_legacy()
            print(f'已验证 {count} 个旧会话可读取')
            print(f'PostgreSQL 账号数：{len(app.state.user_manager.list_users())}')
        finally:
            database.close()


if __name__=='__main__':
    main()
