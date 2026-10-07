from app.database.repositories.base import Repository


class MetricsRepository(Repository):
    def __init__(self, db, lock):
        self.db,self.lock = db,lock

    def summary(self):
        queries = {
            'published_posts':"SELECT COUNT(*) FROM posts WHERE status='published'",
            'posting_users':"SELECT COUNT(DISTINCT user_id) FROM posts WHERE status='published'",
            'published_comments':"SELECT COUNT(*) FROM comments WHERE status='published' AND post_id IN (SELECT id FROM posts WHERE status='published')",
            'answered_posts':"SELECT COUNT(*) FROM posts p WHERE p.status='published' AND EXISTS(SELECT 1 FROM comments c WHERE c.post_id=p.id AND c.status='published' AND c.user_id<>p.user_id)",
            'open_reports':"SELECT COUNT(*) FROM reports WHERE status='open'",
            'hidden_pets':"SELECT COUNT(*) FROM pets WHERE deleted=0 AND hidden=1",
        }
        return {name:self.db.execute(query).fetchone()[0] for name,query in queries.items()}
