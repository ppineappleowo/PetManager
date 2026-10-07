import sqlite3
import json
from threading import RLock
from app.database.repositories.base import Repository


class TurnsRepository(Repository):
    def __init__(self, path, recover=True):
        self.lock = RLock()
        from app.database.postgres import is_postgres, PostgresDatabase
        if is_postgres(path):
            self.db = PostgresDatabase(str(path), 'turns')
            if recover:
              with self.db:
                self.db.execute("UPDATE chat_turns SET status='failed',error='服务已重启，请重试' WHERE status='running'")
            return
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS chat_turns (\n                seq INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,\n                thread_id TEXT NOT NULL, request_id TEXT NOT NULL,\n                prompt TEXT NOT NULL, image_url TEXT, answer TEXT NOT NULL DEFAULT '',\n                status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',\n                UNIQUE(user_id, request_id))")
            self.db.execute('CREATE INDEX IF NOT EXISTS chat_turns_thread ON chat_turns(user_id, thread_id, seq)')
            columns = {r['name'] for r in self.db.execute('PRAGMA table_info(chat_turns)')}
            for name, default in [('sources',"'[]'"),('context',"'{}'"),('feedback',"''"),('feedback_note',"''")]:
                if name not in columns:
                    self.db.execute(f'ALTER TABLE chat_turns ADD COLUMN {name} TEXT NOT NULL DEFAULT {default}')
            if recover:
                self.db.execute("UPDATE chat_turns SET status = 'failed', error = '服务已重启，请重试' WHERE status = 'running'")

    def set_context(self, user_id, request_id, context):
        self.db.execute('UPDATE chat_turns SET context=? WHERE user_id=? AND request_id=?',(json.dumps(context,ensure_ascii=False),user_id,request_id))

    def set_sources(self, user_id, request_id, sources):
        self.db.execute('UPDATE chat_turns SET sources=? WHERE user_id=? AND request_id=?',(json.dumps(sources,ensure_ascii=False),user_id,request_id))

    def feedback(self, user_id, request_id, value, note):
        return self.db.execute("UPDATE chat_turns SET feedback=?,feedback_note=? WHERE user_id=? AND request_id=? AND status='completed'",(value,note,user_id,request_id)).rowcount

    def get_turn(self, user_id, request_id):
        return self.db.execute('SELECT * FROM chat_turns WHERE user_id = ? AND request_id = ?', (user_id, request_id)).fetchone()

    def find_newer_turn(self, user_id, thread_id, row):
        return self.db.execute('SELECT 1 FROM chat_turns WHERE user_id = ? AND thread_id = ? AND seq > ?', (user_id, thread_id, row['seq'])).fetchone()

    def restart_turn(self, row):
        return self.result(self.db.execute("UPDATE chat_turns SET status = 'running', answer = '', error = '' WHERE seq = ?", (row['seq'],)))

    def insert_turn(self, user_id, thread_id, request_id, prompt, image_url):
        return self.result(self.db.execute("INSERT INTO chat_turns(user_id, thread_id, request_id, prompt, image_url, status) VALUES (?, ?, ?, ?, ?, 'running')", (user_id, thread_id, request_id, prompt, image_url)))

    def finish_turn(self, status, answer, error, user_id, request_id):
        return self.result(self.db.execute('UPDATE chat_turns SET status = ?, answer = ?, error = ? WHERE user_id = ? AND request_id = ?', (status, answer, error, user_id, request_id)))

    def list_turns(self, user_id, thread_id):
        return self.db.execute('SELECT * FROM chat_turns WHERE user_id = ? AND thread_id = ? ORDER BY seq', (user_id, thread_id)).fetchall()

    def list_thread_ids(self, user_id):
        return self.db.execute('SELECT thread_id FROM chat_turns WHERE user_id = ? GROUP BY thread_id ORDER BY MAX(seq) DESC', (user_id,)).fetchall()

    def delete_thread(self, user_id, thread_id):
        return self.result(self.db.execute('DELETE FROM chat_turns WHERE user_id = ? AND thread_id = ?', (user_id, thread_id)))
