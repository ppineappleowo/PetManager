from app.database.repositories.base import Repository


class FollowsRepository(Repository):
    def __init__(self, database, lock):
        self.db = database
        self.lock = lock

    def count_connections(self, user_id):
        return self.db.execute('SELECT\n                (SELECT COUNT(*) FROM user_follows f JOIN users u ON u.id=f.followed_id\n                 WHERE f.follower_id=? AND u.disabled=0) AS following_count,\n                (SELECT COUNT(*) FROM user_follows f JOIN users u ON u.id=f.follower_id\n                 WHERE f.followed_id=? AND u.disabled=0) AS follower_count', (user_id, user_id)).fetchone()

    def has_follow(self, actor, target):
        return self.db.execute('SELECT 1 FROM user_follows WHERE follower_id=? AND followed_id=?', (actor, target)).fetchone()

    def lock_users(self, actor, target):
        return self.db.execute('SELECT id,disabled FROM users WHERE id IN (?,?) ORDER BY id FOR SHARE', (actor, target)).fetchall()

    def insert_follow(self, actor, target):
        return self.result(self.db.execute('INSERT INTO user_follows(follower_id,followed_id) VALUES(?,?) ON CONFLICT DO NOTHING', (actor, target)))

    def remove_follow(self, actor, target):
        return self.result(self.db.execute('DELETE FROM user_follows WHERE follower_id=? AND followed_id=?', (actor, target)))

    def list_connections(self, actor, kind, before, limit):
        own, other = ('follower_id', 'followed_id') if kind == 'following' else ('followed_id', 'follower_id')
        where, args = f'f.{own}=? AND u.disabled=0', [actor]
        if before is not None:
            where += ' AND u.id<?'
            args.append(before)
        return self.db.execute(f"""SELECT u.id,u.username,u.nickname,u.phone,u.avatar_id,u.bio,u.profile_hidden,u.avatar_hidden,
            EXISTS(SELECT 1 FROM user_follows mine WHERE mine.follower_id=? AND mine.followed_id=u.id) AS following
            FROM user_follows f JOIN users u ON u.id=f.{other}
            WHERE {where} ORDER BY u.id DESC LIMIT ?""", [actor, *args, limit + 1]).fetchall()
