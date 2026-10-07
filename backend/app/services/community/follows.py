from app.core.errors import BusinessError
from uuid import uuid4

class FollowService:

    def __init__(self, *, repository, notifications):
        self.repository = repository
        self.notifications = notifications

    def follow_counts(self, user_id):
        with self.repository.read():
            row = self.repository.count_connections(user_id)
            return dict(row)

    def follow_state(self, actor, target):
        with self.repository.read():
            return {'following': bool(self.repository.has_follow(actor, target)), 'is_self': actor == target, **self.follow_counts(target)}

    def set_follow(self, actor, target, enabled):
        if actor == target:
            raise BusinessError(422, '不能关注自己')
        with self.repository.transaction():
            users = self.repository.lock_users(actor, target)
            if enabled and (len(users) != 2 or any((row['disabled'] for row in users))):
                raise BusinessError(404, '用户主页不可用')
            if enabled:
                inserted = self.repository.insert_follow(actor, target)
                if inserted.rowcount:
                    self.notifications.emit(target, actor, 'follow', f'follow:{uuid4().hex}')
            else:
                self.repository.remove_follow(actor, target)
            return self.follow_state(actor, target)

    def connections(self, actor, kind, before=None, limit=24):
        from app.services.community.presentation import public_author
        with self.repository.read():
            rows = self.repository.list_connections(actor, kind, before, limit)
        items = [{**public_author(row), 'bio':'' if row['profile_hidden'] else row['bio'], 'following':bool(row['following'])} for row in rows[:limit]]
        return {'items':items, 'next_cursor':items[-1]['id'] if len(rows)>limit else None}
