"""PostgreSQL 连接池与仓储 SQL 适配。业务层不依赖 Redis，也不回退到 SQLite。

保留现有仓储的参数化问号 SQL；集中处理占位符、时间和幂等插入差异。
事务固定使用同一池连接，跨进程 advisory lock 保护原有读改写操作。
"""
import re
import sqlite3
from threading import local,RLock
from time import perf_counter
from app.core.observability import request_metrics
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pools={}
_pool_lock=RLock()


def acquire_pool(url):
    with _pool_lock:
        if url not in _pools:
            _pools[url]=[ConnectionPool(url,min_size=0,max_size=8,timeout=10,
                kwargs={'autocommit':True,'row_factory':dict_row,'connect_timeout':5},open=True),0]
        _pools[url][1]+=1
        return _pools[url][0]


def release_pool(url):
    with _pool_lock:
        entry=_pools[url];entry[1]-=1
        if not entry[1]:
            entry[0].close();del _pools[url]


def is_postgres(value):
    return str(value).startswith(('postgresql://','postgres://'))


class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Result:
    def __init__(self, rows=(), rowcount=0, lastrowid=None):
        self.rows = list(rows)
        self.rowcount = rowcount
        self.lastrowid = lastrowid
    def fetchone(self):
        return self.rows.pop(0) if self.rows else None
    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows
    def __iter__(self):
        return iter(self.fetchall())


def sql_for_postgres(statement):
    statement = statement.strip().rstrip(';')
    statement = statement.replace("strftime('%Y-%m-%dT%H:%M:%fZ','now')", "to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')")
    statement = re.sub(r"datetime\('now'(?:,\s*'-(\d+) days?')?\)",
        lambda m: "to_char((clock_timestamp() AT TIME ZONE 'UTC')" + (f" - interval '{m[1]} days'" if m[1] else '') + ", 'YYYY-MM-DD HH24:MI:SS')", statement)
    ignored = bool(re.match(r'INSERT OR IGNORE\b',statement,re.I))
    statement = re.sub(r'^INSERT OR IGNORE\b','INSERT',statement,flags=re.I)
    if ignored:
        statement += ' ON CONFLICT DO NOTHING'
    table = re.match(r'INSERT INTO\s+(\w+)',statement,re.I)
    serial = {'users':'id','posts':'id','pets':'id','comments':'id','reports':'id','moderation':'id','comment_moderation':'id','chat_turns':'seq'}
    identity = serial.get(table[1].lower()) if table else None
    if identity and 'RETURNING' not in statement.upper():
        statement += ' RETURNING ' + identity
    # 只替换 SQL 字面量以外的占位符，用户数据始终作为参数传递。
    parts = re.split(r"('(?:''|[^'])*')",statement)
    statement = ''.join(part.replace('%','%%').replace('?', '%s') if index % 2 == 0 else part.replace('%','%%') for index,part in enumerate(parts))
    return statement, identity


class PostgresDatabase:
    def __init__(self, url, scope):
        self.scope = scope
        self.local = local()
        self.url=url;self.closed=False
        self.pool = acquire_pool(url)
        # 不在此创建表；schema 迁移由独立命令或应用启动统一执行。
        try:
            self.execute('SELECT 1')
        except BaseException:
            self.close()
            raise

    @contextmanager
    def connection(self):
        current = getattr(self.local,'connection',None)
        if current is not None:
            yield current
        else:
            with self.pool.connection() as connection:
                yield connection

    def __enter__(self):
        if getattr(self.local,'connection',None) is not None:
            raise RuntimeError('Nested repository transactions are not supported')
        self.local.lease = self.pool.connection()
        try:
            self.local.connection = self.local.lease.__enter__()
            self.local.transaction = self.local.connection.transaction()
            self.local.transaction.__enter__()
            self.local.connection.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('baichongji:'+self.scope,))
        except BaseException:
            import sys
            self.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, kind, error, tb):
        try:
            if getattr(self.local,'transaction',None):
                self.local.transaction.__exit__(kind,error,tb)
        finally:
            try:
                if getattr(self.local,'lease',None):
                    self.local.lease.__exit__(kind,error,tb)
            finally:
                self.local.connection = None
                self.local.transaction = None
                self.local.lease = None

    def execute(self, statement, params=()):
        if statement.strip().upper() == 'BEGIN IMMEDIATE':
            if getattr(self.local,'connection',None) is None:
                raise RuntimeError('Write transaction required')
            return Result()
        sql, identity = sql_for_postgres(statement)
        started=perf_counter();stats=request_metrics.get()
        try:
            with self.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql,tuple(params))
                    rows = [Row(row) for row in cursor.fetchall()] if cursor.description else []
                    return Result(rows,cursor.rowcount,rows[0][identity] if identity and rows else None)
        except psycopg.IntegrityError as error:
            # 保持现有仓储唯一冲突的业务错误处理；外层事务负责回滚。
            raise sqlite3.IntegrityError('Database constraint violation') from error
        finally:
            if stats is not None:
                stats['sql_count']+=1;stats['sql_ms']+=(perf_counter()-started)*1000

    def executemany(self, statement, values):
        for params in values:
            self.execute(statement,params)

    def close(self):
        if not self.closed:
            self.closed=True;release_pool(self.url)
