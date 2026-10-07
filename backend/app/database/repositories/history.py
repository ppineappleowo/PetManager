"""PostgreSQL 历史会话访问，统一用户隔离条件。"""
from app.database.postgres import PostgresDatabase
from app.database.legacy.history import LegacyHistory

class HistoryRepository:
    def __init__(self, url):
        self.db = PostgresDatabase(url, 'turns')
        self.legacy = LegacyHistory(self.db)

    def get(self, config):
        return self.legacy.get(config)

    def thread_rows(self, namespace):
        return self.db.execute('SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns = ? ORDER BY thread_id DESC', (namespace,)).fetchall()

    def verify_legacy(self):
        rows = self.db.execute('SELECT DISTINCT thread_id,checkpoint_ns FROM checkpoints').fetchall()
        for row in rows:
            if not isinstance(self.get({'configurable': dict(row)}), dict):
                raise RuntimeError('历史会话读取校验失败')
        return len(rows)

    def clear(self, user_id, thread_id):
        namespace = f'user:{user_id}'
        with self.db:
            self.db.execute('DELETE FROM checkpoints WHERE thread_id=? AND checkpoint_ns=?', (thread_id, namespace))
            self.db.execute('DELETE FROM writes WHERE thread_id=? AND checkpoint_ns=?', (thread_id, namespace))
            self.db.execute('DELETE FROM chat_turns WHERE user_id=? AND thread_id=?', (user_id, thread_id))

    def close(self):
        self.db.close()
