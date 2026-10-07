import json
import os
import unittest
from pathlib import Path
from uuid import uuid4
from app.database.repositories.discovery import search_filters
import test_community
import test_postgres


CASES = [
    ('猫粮', ['猫粮选择']), ('猫', ['猫粮选择', '猫咪晒太阳']),
    ('猫粮 新手', ['猫粮选择']), ('晒宠', ['猫咪晒太阳', '狗狗散步']),
    ('cat', ['CAT 日常']), ('100%', ['100%陪伴']),
    ('a_b', ['a_b 记录']), ('猫量', []), ('不存在的词', []),
]


class DiscoveryTests(unittest.TestCase):
    setUp = test_community.CommunityTests.setUp
    tearDown = test_community.CommunityTests.tearDown
    login = test_community.CommunityTests.login
    token = test_community.CommunityTests.token
    create = test_community.CommunityTests.create

    def test_search_eval_literal_filters_and_order(self):
        records = [('猫粮选择', '新手养宠', 'cat', ['饮食']), ('猫咪晒太阳', '下午的阳光', 'cat', ['晒宠']),
                   ('狗狗散步', '傍晚出门', 'dog', ['晒宠']), ('CAT 日常', '英文记录', 'cat', []),
                   ('100%陪伴', '字面百分号', 'other', []), ('a_b 记录', '字面下划线', 'other', []),
                   ('秘密猫粮', '新手', 'cat', ['隐藏标签'])]
        ids = []
        for title, body, category, tags in records:
            ids.append(self.db.write(1, dict(title=title, body=body, category=category, tags=tags, images=[]), request_key=str(uuid4()))['id'])
        self.db.moderate(ids[-1], 1, 'hidden', '不公开', 1)
        endpoint = '/api/v1/community/posts'
        for query, expected in CASES:
            response = self.client.get(endpoint, params={'q': query})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual({p['title'] for p in response.json()['items']}, set(expected), query)
        self.assertEqual(self.client.get(endpoint, params={'q': "' OR 1=1 --"}).json()['items'], [])
        result = self.client.get(endpoint, params={'q':'晒宠','category':'cat','tag':'晒宠'}).json()
        self.assertEqual([p['id'] for p in result['items']], [ids[1]])
        self.assertEqual(self.client.get(endpoint, params={'tag':'晒'}).json()['items'], [])
        for sort, expected in [('latest', [ids[1],ids[0]]), ('oldest', [ids[0],ids[1]])]:
            first = self.client.get(endpoint, params={'q':'猫','sort':sort,'limit':1}).json()
            second = self.client.get(endpoint, params={'q':'猫','sort':sort,'before':first['next_cursor']}).json()
            self.assertEqual([first['items'][0]['id'], second['items'][0]['id']], expected)
        self.assertEqual(self.client.get(endpoint, params={'q':'x'*101}).status_code, 422)
        self.assertEqual(self.client.get(endpoint, params={'sort':'random'}).status_code, 422)

    def test_topic_counts_edit_hide_delete_and_retry(self):
        first = self.create(tags=['晒宠', '晒宠', '猫咪']).json()
        second = self.create(category='dog', tags=['晒宠']).json()
        url = '/api/v1/community/topics'
        counts = lambda: {t['tag']:t['post_count'] for t in self.client.get(url).json()['items']}
        self.assertEqual(counts(), {'晒宠':2, '猫咪':1})
        self.assertEqual(self.client.get(url, params={'category':'dog','q':'晒'}).json()['items'], [{'tag':'晒宠','post_count':1}])
        self.client.put(f'/api/v1/community/posts/{first["id"]}', headers=self.headers, json={'body':'换个话题','category':'cat','tags':['新话题'],'version':first['version']})
        self.assertEqual(counts(), {'晒宠':1,'新话题':1})
        hidden = self.db.moderate(second['id'], 1, 'hidden', '隐藏', second['version'])
        self.assertEqual(counts(), {'新话题':1})
        self.db.moderate(second['id'], 1, 'published', '恢复', hidden['version'])
        self.assertEqual(counts()['晒宠'], 1)
        self.db.delete(second['id'], 1)
        self.assertEqual(counts(), {'新话题':1})


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == '1', 'Set RUN_POSTGRES_TESTS=1')
class PostgresDiscoveryTests(test_postgres.SchemaTest):
    setUp = test_postgres.PostgresApiTests.setUp
    tearDown = test_postgres.PostgresApiTests.tearDown
    login = test_postgres.PostgresApiTests.login
    token = test_postgres.PostgresApiTests.token
    create = test_postgres.PostgresApiTests.create
    test_eval = DiscoveryTests.test_search_eval_literal_filters_and_order
    test_topics = DiscoveryTests.test_topic_counts_edit_hide_delete_and_retry

    def test_query_plans_and_existing_tag_backfill(self):
        from alembic import command
        from app.database.migrations import alembic_config, sqlalchemy_url
        import sqlalchemy as sa
        engine = sa.create_engine(sqlalchemy_url(self.url))
        try:
            with engine.begin() as conn:
                command.downgrade(alembic_config(conn), '0004_notifications')
                conn.exec_driver_sql("INSERT INTO posts(user_id,title,body,category,tags,images,request_key,payload_hash) SELECT 1,'猫粮经验 '||n,'新手养宠的日常','cat','[\"饮食\",\"晒宠\"]','[]','plan-'||n,'test' FROM generate_series(1,1500) n")
                command.upgrade(alembic_config(conn), 'head')
                self.assertEqual(conn.exec_driver_sql('SELECT COUNT(*) FROM post_tags').scalar(), 3000)
        finally:
            engine.dispose()
        db = self.db.repository.db
        db.execute('ANALYZE posts'); db.execute('ANALYZE post_tags')
        plans = {}
        for name, query, tag in [('中文双词','猫粮 新手',''),('精确标签','','饮食'),('无匹配关键词','不存在的词','')]:
            clauses, args = search_filters(query, tag)
            sql = "SELECT * FROM posts WHERE status='published' AND " + ' AND '.join(clauses) + ' ORDER BY id DESC LIMIT 25'
            plans[name] = db.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql, args).fetchone()[0]
            plans[name+'总数'] = db.execute("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT COUNT(*) FROM posts WHERE status='published' AND " + ' AND '.join(clauses), args).fetchone()[0]
        plans['话题聚合'] = db.execute("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT t.tag,COUNT(*) AS post_count FROM post_tags t JOIN posts ON posts.id=t.post_id WHERE posts.status='published' GROUP BY t.tag ORDER BY post_count DESC,t.tag ASC LIMIT 20").fetchone()[0]
        self.assertEqual(len(self.db.discover(q='猫粮',limit=24)['items']),24)
        if os.getenv('DISCOVERY_PLAN_PATH'):
            output = Path(os.environ['DISCOVERY_PLAN_PATH'])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({'synthetic_posts':1500,'cases':CASES,'plans':plans},ensure_ascii=False,indent=2),encoding='utf-8')
