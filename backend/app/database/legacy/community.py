from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

def migrate_interactions(db, path):
    if db.execute('SELECT 1 FROM community_migrations WHERE version=2').fetchone():
        return
    backup_dir = Path(path).parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f'community-before-v2-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}.db'
    with closing(sqlite3.connect(backup_path)) as backup:
        db.backup(backup)
    try:
        db.executescript("BEGIN IMMEDIATE;\n            CREATE TABLE IF NOT EXISTS comments(\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                post_id INTEGER NOT NULL REFERENCES posts(id), user_id INTEGER NOT NULL,\n                body TEXT NOT NULL, reply_to INTEGER REFERENCES comments(id),\n                status TEXT NOT NULL DEFAULT 'published', reason TEXT NOT NULL DEFAULT '',\n                version INTEGER NOT NULL DEFAULT 1, request_key TEXT NOT NULL,\n                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),\n                UNIQUE(user_id,request_key));\n            CREATE INDEX IF NOT EXISTS comments_post ON comments(post_id,id);\n            CREATE TABLE IF NOT EXISTS post_likes(\n                post_id INTEGER NOT NULL REFERENCES posts(id), user_id INTEGER NOT NULL,\n                PRIMARY KEY(post_id,user_id));\n            CREATE TABLE IF NOT EXISTS comment_moderation(\n                id INTEGER PRIMARY KEY, comment_id INTEGER NOT NULL REFERENCES comments(id),\n                actor_id INTEGER NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL,\n                created_at TEXT NOT NULL DEFAULT (datetime('now')));\n            CREATE TABLE IF NOT EXISTS reports(\n                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,\n                target_type TEXT NOT NULL, target_id INTEGER NOT NULL,\n                post_id INTEGER NOT NULL REFERENCES posts(id), reason TEXT NOT NULL,\n                snapshot TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',\n                resolution TEXT, note TEXT, actor_id INTEGER, resolved_at TEXT,\n                created_at TEXT NOT NULL DEFAULT (datetime('now')),\n                UNIQUE(user_id,target_type,target_id));\n            CREATE INDEX IF NOT EXISTS reports_status ON reports(status,id DESC);\n            INSERT OR IGNORE INTO community_migrations VALUES(2);\n            COMMIT;")
    except BaseException:
        db.rollback()
        raise

def migrate_pets(db, path):
    if db.execute('SELECT 1 FROM community_migrations WHERE version=3').fetchone():
        return
    directory = Path(path).parent / 'backups'
    directory.mkdir(exist_ok=True)
    with closing(sqlite3.connect(directory / f'community-before-v3-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}.db')) as backup:
        db.backup(backup)
    try:
        db.executescript("BEGIN IMMEDIATE;\n            CREATE TABLE IF NOT EXISTS pets(\n                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,\n                name TEXT NOT NULL, species TEXT NOT NULL, breed TEXT NOT NULL DEFAULT '',\n                sex TEXT NOT NULL DEFAULT 'unknown', birthday TEXT, bio TEXT NOT NULL DEFAULT '',\n                photo_id TEXT, version INTEGER NOT NULL DEFAULT 1,\n                deleted INTEGER NOT NULL DEFAULT 0,\n                request_key TEXT NOT NULL, payload_hash TEXT NOT NULL,\n                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),\n                UNIQUE(user_id, request_key));\n            CREATE INDEX IF NOT EXISTS pets_owner ON pets(user_id,deleted,id);\n            CREATE TABLE IF NOT EXISTS post_pets(\n                post_id INTEGER NOT NULL REFERENCES posts(id),\n                pet_id INTEGER NOT NULL REFERENCES pets(id), PRIMARY KEY(post_id,pet_id));\n            CREATE INDEX IF NOT EXISTS pet_posts ON post_pets(pet_id,post_id);\n            INSERT OR IGNORE INTO community_migrations VALUES(3);\n            COMMIT;")
    except BaseException:
        db.rollback()
        raise
