from app.database.repositories.base import Repository


class ReportFeedbackRepository(Repository):
    def __init__(self, db, lock):
        self.db, self.lock = db, lock

    def listing(self, user_id, status, before, limit):
        where, args = ['r.user_id=?'], [user_id]
        if status != 'all':
            where.append('r.status=?')
            args.append(status)
        if before is not None:
            where.append('r.id<?')
            args.append(before)
        return self.db.execute('''SELECT r.id,r.target_type,r.target_id,r.post_id,r.reason,
            r.status,r.resolution,r.note,r.created_at,r.resolved_at,
            p.status AS post_status,c.status AS comment_status
            FROM reports r LEFT JOIN posts p ON p.id=r.post_id
            LEFT JOIN comments c ON r.target_type='comment' AND c.id=r.target_id
            WHERE ''' + ' AND '.join(where) + ' ORDER BY r.id DESC LIMIT ?',
            [*args, limit + 1]).fetchall()
