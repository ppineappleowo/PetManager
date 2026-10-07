"""离线 SQLite → PostgreSQL 数据迁移：原库只读、先备份、事务导入与逐表校验。"""
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
import psycopg
from psycopg import sql
from app.database.setup import initialize_database

TABLES = {
    'users.db': ['users','user_audit'],
    'community.db': ['posts','media','moderation','comments','post_likes','comment_moderation','reports','pets','post_pets','post_bookmarks','notifications','post_tags'],
    'pet.db': ['chat_turns','checkpoints','writes','knowledge_jobs'],
}
ARCHIVED_ONLY = {'sqlite_sequence','community_migrations','auth_attempts','registration_codes'}
SERIAL = {name:'id' for name in ('users','posts','moderation','comments','comment_moderation','reports','pets')}
SERIAL['chat_turns']='seq'
SERIAL['post_bookmarks']='id'
SERIAL['notifications']='id'
TABLES['community.db'].append('community_audit')
SERIAL.update(user_audit='id',community_audit='id')


def read_only(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)


def inspect_sources(root):
    output={}
    for filename in TABLES:
        path=root/filename
        if not path.exists():
            output[filename]={'missing':True}
            continue
        with closing(read_only(path)) as source:
            output[filename]={}
            for (table,) in source.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                quoted='"'+table.replace('"','""')+'"'
                output[filename][table]={'count':source.execute('SELECT COUNT(*) FROM '+quoted).fetchone()[0],
                    'columns':[row[1] for row in source.execute('PRAGMA table_info('+quoted+')')]}
    return output


def digest(rows):
    values=[json.dumps(list(row),ensure_ascii=False,sort_keys=True,default=lambda v:v.astimezone(timezone.utc).isoformat() if isinstance(v,datetime) else bytes(v).hex(),separators=(',',':')) for row in rows]
    return hashlib.sha256('\n'.join(sorted(values)).encode()).hexdigest()


def migrate(root, url, backup_root=None):
    initialize_database(url)
    root=Path(root)
    directory=Path(backup_root or root/'backups')/f"postgres-import-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
    directory.mkdir(parents=True)
    datasets=[]
    for filename, expected in TABLES.items():
        path=root/filename
        if not path.exists():
            continue
        snapshot=directory/filename
        with closing(read_only(path)) as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
        with closing(read_only(snapshot)) as source:
            tables={row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            unknown=tables-set(expected)-ARCHIVED_ONLY
            if unknown:
                raise RuntimeError(f'发现尚未映射的数据表，已停止迁移：{filename}: {sorted(unknown)}')
            for table in expected:
                if table not in tables:
                    continue
                columns=[row[1] for row in source.execute(f'PRAGMA table_info("{table}")')]
                order=' ORDER BY id' if table=='comments' else ''
                rows=source.execute(f'SELECT * FROM "{table}"'+order).fetchall()
                if table in ('post_bookmarks', 'notifications'):
                    timestamps = {index for index, name in enumerate(columns) if name in ('created_at','read_at')}
                    rows = [tuple(datetime.fromisoformat(value).replace(tzinfo=timezone.utc) if index in timestamps and value is not None else value for index, value in enumerate(row)) for row in rows]
                datasets.append((table,columns,rows))
    fingerprint=digest([(table,json.dumps(columns),digest(rows)) for table,columns,rows in datasets])
    report={'backup_directory':str(directory.resolve()),'tables':{},'source_fingerprint':fingerprint}
    with psycopg.connect(url,connect_timeout=5) as target:
        for domain in ('users','community','turns'):
            target.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('baichongji:'+domain,))
        previous=target.execute("SELECT source_fingerprint FROM data_imports WHERE name='sqlite-v1'").fetchone()
        if previous:
            if previous[0]!=fingerprint:
                raise RuntimeError('此目标库已迁移过不同的源数据，拒绝覆盖 PostgreSQL 数据')
            report['already_imported']=True
            return report
        for tables in TABLES.values():
            for table in tables:
                if target.execute(sql.SQL('SELECT 1 FROM {} LIMIT 1').format(sql.Identifier(table))).fetchone():
                    raise RuntimeError(f'目标表 {table} 非空，拒绝覆盖或混合已有数据')
        for table,columns,rows in datasets:
            target_columns={row[0] for row in target.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s',(table,))}
            if not set(columns)<=target_columns:
                raise RuntimeError(f'{table} 存在未映射字段：{set(columns)-target_columns}')
            names=sql.SQL(',').join(map(sql.Identifier,columns))
            insert=sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),names,sql.SQL(',').join(sql.Placeholder() for _ in columns))
            with target.cursor() as cursor:
                cursor.executemany(insert,rows)
            actual=target.execute(sql.SQL('SELECT {} FROM {}').format(names,sql.Identifier(table))).fetchall()
            if len(actual)!=len(rows) or digest(actual)!=digest(rows):
                raise RuntimeError(f'{table} 数据校验失败，事务回滚')
            report['tables'][table]={'rows':len(rows),'verified':True}
        # Old sources may predate the derived tag index.
        target.execute('INSERT INTO post_tags(post_id,tag) SELECT p.id,t.tag FROM posts p CROSS JOIN LATERAL jsonb_array_elements_text(p.tags::jsonb) AS t(tag) ON CONFLICT DO NOTHING')
        for table,column in SERIAL.items():
            target.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s,%s), COALESCE(MAX({}),1), MAX({}) IS NOT NULL) FROM {}").format(sql.Identifier(column),sql.Identifier(column),sql.Identifier(table)),(table,column))
        target.execute("INSERT INTO data_imports(name,source_fingerprint,report) VALUES('sqlite-v1',%s,%s)",(fingerprint,json.dumps(report,ensure_ascii=False)))
    (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
