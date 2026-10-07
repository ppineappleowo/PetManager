from app.core.errors import BusinessError
from app.services.community.presentation import public_author


class NotificationService:
    def __init__(self, repository):
        self.repository = repository

    def emit(self, recipient, actor, kind, event_key, post_id=None, comment_id=None):
        # Called inside the owning business operation's transaction.
        if recipient != actor:
            self.repository.add(recipient, actor, kind, event_key, post_id, comment_id)

    def summary(self, user_id):
        with self.repository.read():
            return self.repository.summary(user_id)

    def listing(self, user_id, users, before=None, limit=24):
        with self.repository.read():
            rows = self.repository.listing(user_id, before, limit)
        actors = users.get_by_ids(row['actor_id'] for row in rows[:limit])
        items = []
        for row in rows[:limit]:
            actor = actors.get(row['actor_id'])
            visible = bool(actor and not actor['disabled']) and (row['kind'] == 'follow' or (row['post_status'] == 'published' and row['comment_status'] == 'published'))
            # No text snapshots: hidden content and identity never appear in placeholders.
            items.append(dict(id=row['id'], kind=row['kind'], created_at=row['created_at'], read=row['read_at'] is not None,
                available=visible, actor=public_author(actor) if visible else None,
                target=(f'/users/{row["actor_id"]}' if row['kind'] == 'follow' else f'/posts/{row["post_id"]}') if visible else None))
        return {'items': items, 'next_cursor': items[-1]['id'] if len(rows) > limit else None}

    def mark_read(self, user_id, notification_id):
        with self.repository.transaction():
            if not self.repository.read_one(user_id, notification_id):
                raise BusinessError(404, '通知不可用')

    def mark_all(self, user_id, through_id):
        with self.repository.transaction():
            self.repository.read_through(user_id, through_id)
