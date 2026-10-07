from app.database.repositories.base import Repository


class NotificationsRepository(Repository):
    def __init__(self, db, lock):
        self.db, self.lock = db, lock

    def add(self, recipient, actor, kind, event_key, post_id=None, comment_id=None):
        self.db.execute('INSERT INTO notifications(recipient_id,actor_id,kind,event_key,post_id,comment_id) VALUES(?,?,?,?,?,?) ON CONFLICT(recipient_id,event_key) DO NOTHING', (recipient, actor, kind, event_key, post_id, comment_id))

    def summary(self, user_id):
        return dict(self.db.execute('SELECT COALESCE(SUM(CASE WHEN read_at IS NULL THEN 1 ELSE 0 END),0) AS unread_count, COALESCE(MAX(id),0) AS latest_id FROM notifications WHERE recipient_id=?', (user_id,)).fetchone())

    def listing(self, user_id, before, limit):
        where, args = 'n.recipient_id=?', [user_id]
        if before is not None:
            where += ' AND n.id<?'
            args.append(before)
        return self.db.execute("""SELECT n.*, p.status AS post_status, c.status AS comment_status
            FROM notifications n LEFT JOIN posts p ON p.id=n.post_id LEFT JOIN comments c ON c.id=n.comment_id
            WHERE """ + where + ' ORDER BY n.id DESC LIMIT ?', [*args, limit + 1]).fetchall()

    def read_one(self, user_id, notification_id):
        return self.result(self.db.execute('UPDATE notifications SET read_at=COALESCE(read_at,CURRENT_TIMESTAMP) WHERE recipient_id=? AND id=?', (user_id, notification_id))).rowcount

    def read_through(self, user_id, through_id):
        self.db.execute('UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE recipient_id=? AND id<=? AND read_at IS NULL', (user_id, through_id))
