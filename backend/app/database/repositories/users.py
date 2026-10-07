import sqlite3
import os
from threading import RLock
from app.database.repositories.base import Repository


class UsersRepository(Repository):
    def get_accounts(self, user_ids):
        ids = list(set(user_ids))
        if not ids:
            return []
        marks = ','.join('?' for _ in ids)
        return self.db.execute(f'SELECT * FROM users WHERE id IN ({marks})', ids).fetchall()

    def __init__(self, db_path: str):
        self.db_path = db_path
        from app.database.postgres import is_postgres, PostgresDatabase
        if is_postgres(db_path):
            self.lock = RLock()
            self.db = PostgresDatabase(db_path, 'users')
            return
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.lock = RLock()
        self.db = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        with self.lock, self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS users (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,\n                created_at TEXT NOT NULL DEFAULT (datetime('now')),\n                role TEXT NOT NULL DEFAULT 'user', token_version INTEGER NOT NULL DEFAULT 0\n            )")
            columns = {row['name'] for row in self.db.execute('PRAGMA table_info(users)')}
            if 'role' not in columns:
                self.db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            if 'token_version' not in columns:
                self.db.execute('ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0')
            if 'disabled' not in columns:
                self.db.execute('ALTER TABLE users ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0')
            for name, definition in [('phone', 'TEXT'), ('nickname', "TEXT NOT NULL DEFAULT ''"), ('bio', "TEXT NOT NULL DEFAULT ''"), ('avatar_id', "TEXT NOT NULL DEFAULT ''")]:
                if name not in columns:
                    self.db.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
            self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_phone ON users(phone) WHERE phone IS NOT NULL')
            self.db.execute('DROP TABLE IF EXISTS registration_codes')
            for name, default in [('profile_hidden',0),('avatar_hidden',0),('profile_version',1)]:
                if name not in columns:
                    self.db.execute(f'ALTER TABLE users ADD COLUMN {name} INTEGER NOT NULL DEFAULT {default}')
            from app.database.repositories.governance import sqlite_audit
            sqlite_audit(self.db,'user_audit')

    def audit_repository(self):
        from app.database.repositories.governance import GovernanceRepository
        return GovernanceRepository(self.db,self.lock,'user_audit')

    def public_search(self,q,before,limit):
        from app.database.repositories.discovery import literal_pattern
        from app.database.postgres import is_postgres
        numeric_phone="username ~ '^[0-9]{11}$'" if is_postgres(self.db_path) else "length(username)=11 AND username NOT GLOB '*[^0-9]*'"
        where=f"disabled=0 AND profile_hidden=0 AND (LOWER(nickname) LIKE ? ESCAPE '!' OR (phone IS NULL AND NOT ({numeric_phone}) AND username NOT LIKE '用户!_%' ESCAPE '!' AND LOWER(username) LIKE ? ESCAPE '!'))"
        args=[literal_pattern(q),literal_pattern(q)]
        if before:where+=' AND id<?';args.append(before)
        return self.db.execute('SELECT * FROM users WHERE '+where+' ORDER BY id DESC LIMIT ?',[*args,limit+1]).fetchall()

    def moderate_profile(self, user_id, field, hidden):
        if field not in ('profile_hidden','avatar_hidden'):
            raise ValueError('Invalid field')
        self.db.execute(f'UPDATE users SET {field}=?,profile_version=profile_version+1 WHERE id=?',(int(hidden),user_id))

    def search_accounts(self, q, offset, limit):
        from app.database.repositories.discovery import literal_pattern
        args = (literal_pattern(q),)
        total = self.db.execute("SELECT COUNT(*) FROM users WHERE LOWER(username) LIKE ? ESCAPE '!'",args).fetchone()[0]
        rows = self.db.execute("SELECT id,username,created_at,role,disabled,nickname,bio,avatar_id,profile_hidden,avatar_hidden,profile_version FROM users WHERE LOWER(username) LIKE ? ESCAPE '!' ORDER BY id DESC LIMIT ? OFFSET ?",(*args,limit,offset)).fetchall()
        return {'items':[dict(row) for row in rows],'total':total}

    def avatar_id(self, user_id):
        return self.db.execute('SELECT avatar_id FROM users WHERE id=?', (user_id,)).fetchone()[0]

    def update_avatar(self, avatar_id, user_id):
        return self.result(self.db.execute('UPDATE users SET avatar_id=?,profile_version=profile_version+1 WHERE id=?', (avatar_id, user_id)))

    def insert_account(self, password_hash, username):
        return self.result(self.db.execute('INSERT INTO users(username, password_hash) VALUES (?, ?)', (username.strip(), password_hash)))

    def find_credentials(self, username):
        return self.db.execute('SELECT * FROM users WHERE username = ? OR phone = ?', (username.strip(), username.strip())).fetchone()

    def phone_exists(self, phone):
        return self.db.execute('SELECT 1 FROM users WHERE phone = ? OR username = ?', (phone, phone)).fetchone()

    def insert_phone_account(self, username, phone, password_hash):
        return self.result(self.db.execute('INSERT INTO users(username, phone, password_hash) VALUES (?, ?, ?)', (username, phone, password_hash)))

    def find_login_id(self, identifier):
        return self.db.execute('SELECT id FROM users WHERE username = ? OR phone = ?', (identifier, identifier)).fetchone()

    def find_name_conflict(self, user_id, username):
        return self.db.execute('SELECT id FROM users WHERE id != ? AND (username = ? OR phone = ?)', (user_id, username, username)).fetchone()

    def update_profile(self, username, nickname, bio, user_id):
        return self.result(self.db.execute('UPDATE users SET username = ?, nickname = ?, bio = ?,profile_version=profile_version+1 WHERE id = ?', (username, nickname, bio, user_id)))

    def list_accounts(self):
        return self.db.execute('SELECT id, username, created_at, role, disabled FROM users ORDER BY id DESC').fetchall()

    def get_account_for_update(self, user_id):
        return self.db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    def count_active_admins(self):
        return self.db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND disabled = 0").fetchone()[0]

    def update_access(self, new_role, new_disabled, user_id, revoke, row):
        return self.result(self.db.execute('UPDATE users SET role = ?, disabled = ?, token_version = token_version + ? WHERE id = ?', (new_role, new_disabled, int(revoke or new_disabled != row['disabled']), user_id)))

    def get_account(self, user_id):
        return self.db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    def get_credentials(self, user_id):
        return self.db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    def update_password(self, new_hash, user_id, token_version):
        return self.result(self.db.execute('UPDATE users SET password_hash = ?, token_version = token_version + 1\n                    WHERE id = ? AND token_version = ?', (new_hash, user_id, token_version)))

    def update_role(self, role, username):
        return self.db.execute('UPDATE users SET role = ? WHERE username = ?', (role, username)).rowcount
