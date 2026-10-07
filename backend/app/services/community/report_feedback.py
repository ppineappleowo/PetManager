class ReportFeedbackService:
    def __init__(self, repository):
        self.repository = repository

    def listing(self, user_id, status='all', before=None, limit=20):
        with self.repository.read():
            rows = self.repository.listing(user_id, status, before, limit)
        items = []
        for row in rows[:limit]:
            # Only the reporter's own input and the public handling explanation.
            # Evidence snapshots and moderator identity remain admin-only.
            item = {key: row[key] for key in ('id', 'target_type', 'target_id', 'reason',
                'status', 'resolution', 'note', 'created_at', 'resolved_at')}
            visible = row['post_status'] == 'published' and (
                row['target_type'] == 'post' or row['comment_status'] == 'published')
            item['target'] = f'/posts/{row["post_id"]}' if visible else None
            items.append(item)
        return {'items': items, 'next_cursor': items[-1]['id'] if len(rows) > limit else None}
