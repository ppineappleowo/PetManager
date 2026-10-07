from threading import RLock
from app.database.postgres import PostgresDatabase
from app.database.repositories.base import Repository


class KnowledgeJobsRepository(Repository):
    def __init__(self,url):
        self.db=PostgresDatabase(url,'knowledge');self.lock=RLock()

    def add(self,job_id,actor,source,payload):
        self.db.execute('INSERT INTO knowledge_jobs(id,actor_id,source,payload) VALUES(?,?,?,?)',(job_id,actor,source,payload))

    def get(self,job_id):
        return self.db.execute('SELECT * FROM knowledge_jobs WHERE id=?',(job_id,)).fetchone()

    def claim(self,job_id):
        return self.db.execute("UPDATE knowledge_jobs SET status='building',error='',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status IN ('queued','failed')",(job_id,)).rowcount

    def finish(self,job_id,status,error='',version=''):
        self.db.execute("UPDATE knowledge_jobs SET status=?,error=?,version=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(status,error,version,job_id))

    def listing(self,offset,limit):
        rows=self.db.execute('SELECT id,source,status,error,version,created_at,updated_at FROM knowledge_jobs ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',(limit,offset)).fetchall()
        return {'items':[dict(r) for r in rows],'total':self.db.execute('SELECT COUNT(*) FROM knowledge_jobs').fetchone()[0]}

    def recover(self):
        self.db.execute("UPDATE knowledge_jobs SET status='failed',error='服务已重启，请重试' WHERE status='building'")
