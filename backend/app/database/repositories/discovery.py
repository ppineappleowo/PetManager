from app.database.repositories.base import Repository


def literal_pattern(value):
    return '%' + value.lower().replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'


def search_filters(query, tag):
    clauses, args = [], []
    for word in query.split():
        clauses.append("(LOWER(title) LIKE ? ESCAPE '!' OR LOWER(body) LIKE ? ESCAPE '!' OR EXISTS (SELECT 1 FROM post_tags st WHERE st.post_id=posts.id AND LOWER(st.tag) LIKE ? ESCAPE '!'))")
        args.extend([literal_pattern(word)] * 3)
    if tag:
        clauses.append('EXISTS (SELECT 1 FROM post_tags st WHERE st.post_id=posts.id AND st.tag=?)')
        args.append(tag)
    return clauses, args


class DiscoveryRepository(Repository):
    def __init__(self, db, lock):
        self.db, self.lock = db, lock

    def topics(self, category=None, q='', limit=20):
        where, args = "posts.status='published'", []
        if category:
            where += ' AND posts.category=?'
            args.append(category)
        if q:
            where += " AND LOWER(t.tag) LIKE ? ESCAPE '!'"
            args.append(literal_pattern(q))
        with self.read():
            rows = self.db.execute('SELECT t.tag,COUNT(*) AS post_count FROM post_tags t JOIN posts ON posts.id=t.post_id WHERE ' + where + ' GROUP BY t.tag ORDER BY post_count DESC,t.tag ASC LIMIT ?', [*args, limit]).fetchall()
        return [dict(row) for row in rows]
