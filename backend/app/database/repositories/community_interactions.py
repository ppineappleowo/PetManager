import json
from app.database.repositories.base import Repository


class InteractionsRepository(Repository):
    def __init__(self, database, lock):
        self.db = database
        self.lock = lock

    def count_likes(self, post_id):
        return self.db.execute('SELECT COUNT(*) FROM post_likes WHERE post_id=?', (post_id,)).fetchone()[0]

    def count_comments(self, post_id):
        return self.db.execute("SELECT COUNT(*) FROM comments WHERE post_id=? AND status='published'", (post_id,)).fetchone()[0]

    def has_like(self, post_id, user_id):
        return self.db.execute('SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?', (post_id, user_id)).fetchone()

    def insert_like(self, post_id, user_id):
        return self.result(self.db.execute('INSERT OR IGNORE INTO post_likes(post_id,user_id) VALUES(?,?)', (post_id, user_id)))

    def remove_like(self, post_id, user_id):
        return self.result(self.db.execute('DELETE FROM post_likes WHERE post_id=? AND user_id=?', (post_id, user_id)))

    def get_comment(self, comment_id):
        return self.db.execute('SELECT * FROM comments WHERE id=?', (comment_id,)).fetchone()

    def find_comment_request(self, user_id, request_key):
        return self.db.execute('SELECT * FROM comments WHERE user_id=? AND request_key=?', (user_id, request_key)).fetchone()

    def insert_comment(self, post_id, user_id, body, reply_to, request_key):
        return self.result(self.db.execute('INSERT INTO comments(post_id,user_id,body,reply_to,request_key) VALUES(?,?,?,?,?)', (post_id, user_id, body, reply_to, request_key)))

    def list_comments(self, post_id, after, limit):
        return self.db.execute('SELECT * FROM comments WHERE post_id=? AND id>? ORDER BY id LIMIT ?', (post_id, after, limit + 1)).fetchall()

    def delete_comment(self, comment_id):
        return self.result(self.db.execute("UPDATE comments SET status='deleted',version=version+1 WHERE id=?", (comment_id,)))

    def update_comment_status(self, status, reason, comment_id):
        return self.result(self.db.execute('UPDATE comments SET status=?,reason=?,version=version+1 WHERE id=?', (status, reason, comment_id)))

    def audit_comment(self, comment_id, actor_id, status, reason):
        return self.result(self.db.execute('INSERT INTO comment_moderation(comment_id,actor_id,action,reason) VALUES(?,?,?,?)', (comment_id, actor_id, status, reason)))

    def audit_repository(self):
        from app.database.repositories.governance import GovernanceRepository
        return GovernanceRepository(self.db,self.lock,'community_audit')

    def insert_report(self, user_id, target_type, target_id, post_id, reason, snapshot):
        return self.result(self.db.execute('INSERT OR IGNORE INTO reports(user_id,target_type,target_id,post_id,reason,snapshot) VALUES(?,?,?,?,?,?)', (user_id, target_type, target_id, post_id, reason, json.dumps(snapshot, ensure_ascii=False))))

    def find_report(self, user_id, target_type, target_id):
        return self.db.execute('SELECT id,status FROM reports WHERE user_id=? AND target_type=? AND target_id=?', (user_id, target_type, target_id)).fetchone()

    def count_reports(self, status):
        return self.db.execute('SELECT COUNT(*) FROM reports WHERE status=?', (status,)).fetchone()[0]

    def list_reports(self, status, limit, offset):
        return self.db.execute('SELECT * FROM reports WHERE status=? ORDER BY id DESC LIMIT ? OFFSET ?', (status, limit, offset)).fetchall()

    def get_report(self, report_id):
        return self.db.execute('SELECT * FROM reports WHERE id=?', (report_id,)).fetchone()

    def hide_report_target(self, target_type, target_id, actor_id, note):
        table, audit, key = ('posts', 'moderation', 'post_id') if target_type == 'post' else ('comments', 'comment_moderation', 'comment_id')
        target = self.db.execute(f'SELECT status,version,user_id FROM {table} WHERE id=?', (target_id,)).fetchone()
        if target['status'] == 'published':
            self.db.execute(f"UPDATE {table} SET status='hidden',reason=?,version=version+1 WHERE id=?", (note, target_id))
            self.db.execute(f'INSERT INTO {audit}({key},actor_id,action,reason) VALUES(?,?,?,?)', (target_id, actor_id, 'hidden', note))
            self.audit_repository().add(target['user_id'],actor_id,target_type,target_id,note,
                {'status':target['status'],'version':target['version']},{'status':'hidden','version':target['version']+1})

    def resolve_report(self, action, note, actor_id, report_id):
        return self.result(self.db.execute("UPDATE reports SET status='resolved',resolution=?,note=?,actor_id=?,resolved_at=datetime('now') WHERE id=?", (action, note, actor_id, report_id)))

    def list_admin_comments(self, post_id, offset, limit):
        where, args = ('post_id=?', [post_id]) if post_id is not None else ('1=1', [])
        total = self.db.execute('SELECT COUNT(*) FROM comments WHERE '+where,args).fetchone()[0]
        rows = self.db.execute('SELECT * FROM comments WHERE '+where+' ORDER BY id DESC LIMIT ? OFFSET ?', [*args,limit,offset]).fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data.pop('request_key')
            data['audit'] = [dict(r) for r in self.db.execute('SELECT actor_id,action,reason,created_at FROM comment_moderation WHERE comment_id=? ORDER BY id DESC',(data['id'],))]
            items.append(data)
        return {'items':items,'total':total}
