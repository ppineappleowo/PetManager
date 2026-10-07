"""Moderation records contain public profile fields only, never credentials."""
import json
from app.database.repositories.base import Repository


class GovernanceRepository(Repository):
    def __init__(self, db, lock, table):
        if table not in ('user_audit', 'community_audit'):
            raise ValueError('Invalid audit table')
        self.db, self.lock, self.table = db, lock, table

    def add(self, owner, actor, kind, target, reason, before, after):
        self.db.execute(f'INSERT INTO {self.table}(owner_id,actor_id,kind,target_id,reason,before_state,after_state) VALUES(?,?,?,?,?,?,?)',
            (owner, actor, kind, target, reason, json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))

    def listing(self, owner=None, before=None, limit=20):
        where, args = ['1=1'], []
        if owner is not None:
            where.append('owner_id=?'); args.append(owner)
        if before is not None:
            where.append('id<?'); args.append(before)
        rows = self.db.execute(f'SELECT * FROM {self.table} WHERE ' + ' AND '.join(where) + ' ORDER BY id DESC LIMIT ?', [*args, limit+1]).fetchall()
        items = []
        for row in rows[:limit]:
            item = dict(row)
            if owner is not None:
                after=json.loads(item['after_state'])
                item = {key: item[key] for key in ('id','kind','target_id','reason','created_at')}
                item['result']={k:v for k,v in after.items() if k in ('status','hidden','profile_hidden','avatar_hidden','role','disabled','revoked')}
            else:
                for key in ('before_state','after_state'):
                    item[key] = json.loads(item[key])
            items.append(item)
        return {'items':items, 'next_cursor':items[-1]['id'] if len(rows)>limit else None}


def sqlite_audit(db, table):
    if table not in ('user_audit', 'community_audit'):
        raise ValueError('Invalid audit table')
    db.execute(f'''CREATE TABLE IF NOT EXISTS {table}(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,actor_id INTEGER NOT NULL,kind TEXT NOT NULL,target_id INTEGER NOT NULL,
        reason TEXT NOT NULL,before_state TEXT NOT NULL,after_state TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))''')
    db.execute(f'CREATE INDEX IF NOT EXISTS {table}_owner ON {table}(owner_id,id)')
