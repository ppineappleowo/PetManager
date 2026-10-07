class BookmarkService:
    def __init__(self, repository, get_post, decode):
        self.repository, self.get_post, self.decode = repository, get_post, decode

    def state(self, user_id, post_id):
        with self.repository.read():
            self.get_post(post_id)
            return {'bookmarked': self.repository.contains(user_id, post_id)}

    def set(self, user_id, post_id, enabled):
        with self.repository.transaction():
            if enabled:
                self.get_post(post_id)
                self.repository.add(user_id, post_id)
            else:
                # Removing one's own relationship remains safe after a post is hidden.
                self.repository.remove(user_id, post_id)
        return {'bookmarked': enabled}

    def listing(self, user_id, before=None, limit=24):
        with self.repository.read():
            rows = self.repository.listing(user_id, before, limit)
        items = [self.decode(row) for row in rows[:limit]]
        cursor = items[-1]['bookmark_id'] if len(rows) > limit else None
        for item in items:
            item.pop('bookmark_id')
        return {'items': items, 'next_cursor': cursor}
