import json
import base64
import tempfile
from pathlib import Path
from threading import Lock,RLock
from uuid import uuid4
from app.core.errors import BusinessError
from app.database.repositories.knowledge_jobs import KnowledgeJobsRepository


class KnowledgeJobs:
    def __init__(self,url,chunk_size=500,chunk_overlap=100):
        self.url=url;self.repository=None;self.lock=Lock();self.init_lock=RLock()
        self.chunk_size=chunk_size;self.chunk_overlap=chunk_overlap

    def payload(self,data):
        return json.dumps({**data,'chunk_size':self.chunk_size,'chunk_overlap':self.chunk_overlap},ensure_ascii=False)

    def initialize(self):
        with self.init_lock:
            if self.repository is None:
                repo=KnowledgeJobsRepository(self.url)
                try:
                    with repo.transaction():repo.recover()
                except BaseException:repo.close();raise
                self.repository=repo

    def listing(self,offset=0,limit=20):
        self.initialize()
        return self.repository.listing(offset,limit)

    def create(self,actor,source,text):
        self.initialize();job_id=uuid4().hex
        with self.repository.transaction():self.repository.add(job_id,actor,source,self.payload({'text':text}))
        return {'id':job_id,'status':'queued'}

    def create_documents(self,source,docs,metas,docs_hash):
        self.initialize();job_id=uuid4().hex
        with self.repository.transaction():self.repository.add(job_id,0,source,json.dumps({'documents':docs,'metadatas':metas,'docs_hash':docs_hash},ensure_ascii=False))
        return job_id

    def create_files(self,files,docs_hash):
        self.initialize();job_id=uuid4().hex
        with self.repository.transaction():self.repository.add(job_id,0,'本地知识文件',self.payload({'files':files,'docs_hash':docs_hash}))
        return job_id

    def run(self,job_id,rag):
        self.initialize()
        if not self.lock.acquire(blocking=False):
            raise BusinessError(409,'已有导入任务正在执行')
        try:
            with self.repository.transaction():
                row=self.repository.get(job_id)
                if not row:raise BusinessError(404,'导入任务不存在')
                if row['status']=='completed':return {'id':job_id,'status':'completed','version':row['version']}
                if not self.repository.claim(job_id):raise BusinessError(409,'任务正在执行，请刷新')
            try:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                payload=json.loads(row['payload'])
                splitter=RecursiveCharacterTextSplitter(chunk_size=payload.get('chunk_size',self.chunk_size),chunk_overlap=payload.get('chunk_overlap',self.chunk_overlap))
                with rag.repository.lock:
                    # Reconcile a published index if the process stopped before its SQL completion record.
                    if getattr(rag.repository,'metadata',{}).get('build_id')==job_id:
                        version=rag.repository.version_list()['active']
                        with self.repository.transaction():self.repository.finish(job_id,'completed',version=version)
                        return {'id':job_id,'status':'completed','version':version}
                    if 'documents' in payload:
                        docs,metas=payload['documents'],payload['metadatas']
                    elif 'files' in payload:
                        from app.services.ai.agent import _load_file_as_docs
                        raw=[]
                        with tempfile.TemporaryDirectory() as directory:
                            for file in payload['files']:
                                filename=Path(file['name']).name
                                path=Path(directory)/filename
                                path.write_bytes(base64.b64decode(file['data']))
                                raw.extend(_load_file_as_docs(str(path),filename))
                        chunks=splitter.split_documents(raw)
                        if not chunks:raise ValueError('Empty source')
                        old=rag.repository.get(include=['documents','metadatas'])
                        keep=[i for i,m in enumerate(old.get('metadatas') or []) if (m or {}).get('origin') in ('upload','manual')]
                        docs=[old['documents'][i] for i in keep]+[c.page_content for c in chunks]
                        metas=[old['metadatas'][i] for i in keep]+[{**c.metadata,'origin':'local'} for c in chunks]
                    else:
                        chunks=splitter.split_text(payload['text'])
                        if not chunks:raise ValueError('Empty source')
                        old=rag.repository.get(include=['documents','metadatas'])
                        keep=[i for i,m in enumerate(old.get('metadatas') or []) if (m or {}).get('source')!=row['source']]
                        docs=[old['documents'][i] for i in keep]+chunks
                        metas=[old['metadatas'][i] or {'source':'manual'} for i in keep]+[{'source':row['source'],'origin':'upload'} for _ in chunks]
                    version=rag.rebuild_documents(docs,metas,payload.get('docs_hash',''),build_id=job_id)
                with self.repository.transaction():self.repository.finish(job_id,'completed',version=version)
            except Exception as error:
                with self.repository.transaction():self.repository.finish(job_id,'failed',error=type(error).__name__+'：导入失败，原索引继续可用，请重试')
                raise BusinessError(503,'导入失败，原知识索引继续可用，可重试任务') from None
            return {'id':job_id,'status':'completed','version':version}
        finally:self.lock.release()

    def close(self):
        if self.repository:self.repository.close()
