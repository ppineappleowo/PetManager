"""数据库会话及事务边界；不依赖 HTTP 或业务服务。"""
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class WriteResult:
    lastrowid: int | None
    rowcount: int


class Repository:
    @staticmethod
    def result(cursor):
        return WriteResult(getattr(cursor, "lastrowid", None), getattr(cursor, "rowcount", 0))

    @contextmanager
    def read(self):
        with self.lock:
            yield self

    @contextmanager
    def transaction(self):
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            yield self

    def ping(self):
        with self.read():
            self.db.execute("SELECT 1")

    def close(self):
        with self.lock:
            self.db.close()
