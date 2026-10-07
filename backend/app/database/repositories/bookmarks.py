from app.database.repositories.base import Repository


class BookmarksRepository(Repository):
    def __init__(self, db, lock):
        self.db, self.lock = db, lock

    def contains(self, user_id, post_id):
        return bool(self.db.execute('SELECT 1 FROM post_bookmarks WHERE user_id=? AND post_id=?', (user_id, post_id)).fetchone())

    def add(self, user_id, post_id):
        self.db.execute('INSERT INTO post_bookmarks(user_id,post_id) VALUES(?,?) ON CONFLICT(user_id,post_id) DO NOTHING', (user_id, post_id))

    def remove(self, user_id, post_id):
        self.db.execute('DELETE FROM post_bookmarks WHERE user_id=? AND post_id=?', (user_id, post_id))

    def listing(self, user_id, before, limit):
        where = "b.user_id=? AND p.status='published'"
        args = [user_id]
        if before is not None:
            where += ' AND b.id<?'
            args.append(before)
        return self.db.execute('SELECT p.*, b.id AS bookmark_id FROM post_bookmarks b JOIN posts p ON p.id=b.post_id WHERE ' + where + ' ORDER BY b.id DESC LIMIT ?', [*args, limit + 1]).fetchall()
