import sqlite3
from pathlib import Path
from threading import RLock
from app.database.repositories.base import Repository
from app.database.legacy.community import migrate_interactions, migrate_pets
from app.database.repositories.discovery import search_filters, DiscoveryRepository


class PostsRepository(Repository):
    def presentation_data(self, post_ids):
        ids = list(set(post_ids))
        counts = {post_id: {'like_count': 0, 'comment_count': 0} for post_id in ids}
        pets = {post_id: [] for post_id in ids}
        if not ids:
            return counts, pets
        marks = ','.join('?' for _ in ids)
        with self.read():
            # Separate aggregates avoid multiplying likes by comments or pets.
            for row in self.db.execute(f'SELECT post_id, COUNT(*) AS total FROM post_likes WHERE post_id IN ({marks}) GROUP BY post_id', ids).fetchall():
                counts[row['post_id']]['like_count'] = row['total']
            for row in self.db.execute(f"SELECT post_id, COUNT(*) AS total FROM comments WHERE status='published' AND post_id IN ({marks}) GROUP BY post_id", ids).fetchall():
                counts[row['post_id']]['comment_count'] = row['total']
            rows = self.db.execute(f'SELECT pp.post_id, p.* FROM post_pets pp JOIN pets p ON p.id=pp.pet_id WHERE p.deleted=0 AND p.hidden=0 AND pp.post_id IN ({marks}) ORDER BY pp.post_id,p.id', ids).fetchall()
            for row in rows:
                pets[row['post_id']].append(dict(row))
        return counts, pets

    def __init__(self, path):
        from app.database.postgres import is_postgres, PostgresDatabase
        if is_postgres(path):
            self.lock = RLock()
            self.db = PostgresDatabase(str(path), 'community')
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        with self.db:
            self.db.executescript("\n                CREATE TABLE IF NOT EXISTS community_migrations(version INTEGER PRIMARY KEY);\n                CREATE TABLE IF NOT EXISTS posts(\n                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,\n                    title TEXT NOT NULL, body TEXT NOT NULL, category TEXT NOT NULL,\n                    tags TEXT NOT NULL, images TEXT NOT NULL,\n                    status TEXT NOT NULL DEFAULT 'published', reason TEXT NOT NULL DEFAULT '',\n                    version INTEGER NOT NULL DEFAULT 1,\n                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),\n                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),\n                    request_key TEXT NOT NULL, payload_hash TEXT NOT NULL,\n                    UNIQUE(user_id, request_key));\n                CREATE INDEX IF NOT EXISTS posts_feed ON posts(status, id DESC);\n                CREATE INDEX IF NOT EXISTS posts_category ON posts(status, category, id DESC);\n                CREATE INDEX IF NOT EXISTS posts_owner ON posts(user_id, id DESC);\n                CREATE TABLE IF NOT EXISTS media(\n                    id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, ready INTEGER NOT NULL DEFAULT 0,\n                    touched_at TEXT NOT NULL DEFAULT (datetime('now')));\n                CREATE TABLE IF NOT EXISTS moderation(\n                    id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL REFERENCES posts(id),\n                    actor_id INTEGER NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL,\n                    created_at TEXT NOT NULL DEFAULT (datetime('now')));\n                INSERT OR IGNORE INTO community_migrations VALUES (1);\n            ")
        try:
            migrate_interactions(self.db, path)
            migrate_pets(self.db, path)
            with self.db:
                self.db.executescript('CREATE TABLE IF NOT EXISTS post_tags(post_id INTEGER NOT NULL REFERENCES posts(id), tag TEXT NOT NULL, PRIMARY KEY(post_id,tag)); CREATE INDEX IF NOT EXISTS post_tags_tag ON post_tags(tag,post_id);')
                if not self.db.execute('SELECT 1 FROM community_migrations WHERE version=4').fetchone():
                    self.db.execute('INSERT OR IGNORE INTO post_tags(post_id,tag) SELECT posts.id,j.value FROM posts,json_each(posts.tags) j')
                    self.db.execute('INSERT INTO community_migrations VALUES(4)')
            with self.db:
                self.db.executescript("CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_id INTEGER NOT NULL, actor_id INTEGER NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('comment','reply','follow')), event_key TEXT NOT NULL, post_id INTEGER REFERENCES posts(id), comment_id INTEGER REFERENCES comments(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, read_at TEXT, UNIQUE(recipient_id,event_key)); CREATE INDEX IF NOT EXISTS notifications_recipient ON notifications(recipient_id,id); CREATE INDEX IF NOT EXISTS notifications_unread ON notifications(recipient_id,id) WHERE read_at IS NULL;")
            with self.db:
                self.db.executescript('CREATE TABLE IF NOT EXISTS post_bookmarks(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, post_id INTEGER NOT NULL REFERENCES posts(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,post_id)); CREATE INDEX IF NOT EXISTS post_bookmarks_owner ON post_bookmarks(user_id,id);')
                columns = {r['name'] for r in self.db.execute('PRAGMA table_info(pets)')}
                if 'hidden' not in columns:
                    self.db.execute('ALTER TABLE pets ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0')
                from app.database.repositories.governance import sqlite_audit
                sqlite_audit(self.db,'community_audit')
                post_columns={r['name'] for r in self.db.execute('PRAGMA table_info(posts)')}
                if 'ai_generated' not in post_columns:
                    self.db.execute('ALTER TABLE posts ADD COLUMN ai_generated INTEGER NOT NULL DEFAULT 0')
        except BaseException:
            self.db.close()
            raise

    def get_post(self, post_id):
        return self.db.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()

    def mark_ai_generated(self,post_id):
        self.db.execute('UPDATE posts SET ai_generated=1 WHERE id=?',(post_id,))

    def list_posts(self, category=None, before=None, owner=None, limit=24, admin=False, offset=0, q='', author=None, pet_id=None, following=None, search='', tag='', sort='latest'):
        clauses, args = ([], [])
        if not admin:
            clauses.append("status != 'deleted'" if owner is not None else "status = 'published'")
        if owner is not None:
            clauses.append('user_id=?')
            args.append(owner)
        if author is not None:
            clauses.append('user_id=?')
            args.append(author)
        if following is not None:
            clauses.append('user_id IN (SELECT f.followed_id FROM user_follows f JOIN users u ON u.id=f.followed_id WHERE f.follower_id=? AND u.disabled=0)')
            args.append(following)
        if category:
            clauses.append('category=?')
            args.append(category)
        if pet_id is not None:
            clauses.append('id IN (SELECT post_id FROM post_pets WHERE pet_id=?)')
            args.append(pet_id)
        if before:
            clauses.append('id>?' if sort == 'oldest' else 'id<?')
            args.append(before)
        if q:
            clauses.append('(title LIKE ? OR body LIKE ?)')
            args.extend(['%' + q + '%'] * 2)
        discovery_clauses, discovery_args = search_filters(search, tag)
        clauses.extend(discovery_clauses)
        args.extend(discovery_args)
        where = ' AND '.join(clauses) or '1=1'
        with self.lock:
            total = self.db.execute('SELECT COUNT(*) FROM posts WHERE ' + where, args).fetchone()[0]
            direction = 'ASC' if sort == 'oldest' else 'DESC'
            rows = self.db.execute('SELECT * FROM posts WHERE ' + where + ' ORDER BY id ' + direction + ' LIMIT ? OFFSET ?', [*args, limit + 1, offset]).fetchall()
        items = [dict(row) for row in rows[:limit]]
        return {'items': items, 'next_cursor': items[-1]['id'] if len(rows) > limit else None, 'total': total}

    def get_owned_ready_media(self, image, user_id):
        return self.db.execute('SELECT * FROM media WHERE id=? AND user_id=? AND ready=1', (image, user_id)).fetchone()

    def find_post_request(self, user_id, request_key):
        return self.db.execute('SELECT * FROM posts WHERE user_id=? AND request_key=?', (user_id, request_key)).fetchone()

    def insert_post(self, user_id, request_key, digest, values):
        return self.db.execute('INSERT INTO posts(title,body,category,tags,images,user_id,request_key,payload_hash) VALUES(?,?,?,?,?,?,?,?)', (*values, user_id, request_key, digest)).lastrowid

    def replace_tags(self, post_id, tags):
        self.db.execute('DELETE FROM post_tags WHERE post_id=?', (post_id,))
        self.db.executemany('INSERT INTO post_tags(post_id,tag) VALUES(?,?) ON CONFLICT DO NOTHING', [(post_id, tag) for tag in tags])

    def topics(self, category, q, limit):
        return DiscoveryRepository(self.db, self.lock).topics(category, q, limit)

    def update_post(self, post_id, values):
        return self.result(self.db.execute("UPDATE posts SET title=?,body=?,category=?,tags=?,images=?,version=version+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (*values, post_id)))

    def remove_post_pet_links(self, post_id):
        return self.result(self.db.execute('DELETE FROM post_pets WHERE post_id=?', (post_id,)))

    def insert_post_pet_links(self, post_id, pet_ids):
        return self.result(self.db.executemany('INSERT INTO post_pets(post_id,pet_id) VALUES(?,?)', [(post_id, pet_id) for pet_id in pet_ids]))

    def touch_media(self, user_id):
        return self.result(self.db.execute("UPDATE media SET touched_at=datetime('now') WHERE user_id=?", (user_id,)))

    def delete_post(self, post_id):
        return self.result(self.db.execute("UPDATE posts SET status='deleted',version=version+1 WHERE id=?", (post_id,)))

    def touch_deleted_post_media(self, user_id):
        return self.result(self.db.execute("UPDATE media SET touched_at=datetime('now') WHERE user_id=?", (user_id,)))

    def update_post_status(self, status, reason, post_id):
        return self.result(self.db.execute('UPDATE posts SET status=?,reason=?,version=version+1 WHERE id=?', (status, reason, post_id)))

    def audit_post(self, post_id, actor, status, reason):
        return self.result(self.db.execute('INSERT INTO moderation(post_id,actor_id,action,reason) VALUES(?,?,?,?)', (post_id, actor, status, reason)))

    def insert_media(self, media_id, user_id):
        return self.result(self.db.execute('INSERT INTO media(id,user_id) VALUES(?,?)', (media_id, user_id)))

    def mark_media_ready(self, media_id):
        return self.result(self.db.execute('UPDATE media SET ready=1 WHERE id=?', (media_id,)))

    def has_owned_media(self, media_id, user_id):
        return self.db.execute('SELECT 1 FROM media WHERE id=? AND user_id=? AND ready=1', (media_id, user_id)).fetchone()

    def post_media_references(self):
        return self.db.execute("SELECT images FROM posts WHERE status!='deleted'").fetchall()

    def pet_media_references(self):
        return self.db.execute('SELECT photo_id FROM pets WHERE deleted=0 AND photo_id IS NOT NULL').fetchall()

    def expired_media(self):
        return self.db.execute("SELECT id FROM media WHERE touched_at < datetime('now','-1 day')").fetchall()

    def remove_media(self, row):
        return self.result(self.db.execute('DELETE FROM media WHERE id=?', (row['id'],)))

    def related(self):
        from app.database.repositories.community_interactions import InteractionsRepository
        from app.database.repositories.community_pets import PetsRepository
        from app.database.repositories.community_follows import FollowsRepository
        return (InteractionsRepository(self.db, self.lock), PetsRepository(self.db, self.lock), FollowsRepository(self.db, self.lock))

    def bookmarks_repository(self):
        from app.database.repositories.bookmarks import BookmarksRepository
        return BookmarksRepository(self.db, self.lock)

    def notifications_repository(self):
        from app.database.repositories.notifications import NotificationsRepository
        return NotificationsRepository(self.db, self.lock)

    def report_feedback_repository(self):
        from app.database.repositories.report_feedback import ReportFeedbackRepository
        return ReportFeedbackRepository(self.db, self.lock)

    def audit_repository(self):
        from app.database.repositories.governance import GovernanceRepository
        return GovernanceRepository(self.db,self.lock,'community_audit')

    def metrics(self):
        from app.database.repositories.community_metrics import MetricsRepository
        with self.read():
            return MetricsRepository(self.db,self.lock).summary()

    def moderation_history(self, post_id):
        with self.read():
            return [dict(row) for row in self.db.execute('SELECT actor_id,action,reason,created_at FROM moderation WHERE post_id=? ORDER BY id DESC', (post_id,))]
