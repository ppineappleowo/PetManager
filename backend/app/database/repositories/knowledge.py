"""Chroma 向量集合适配；检索策略由业务层负责。"""
import chromadb
import json
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4
from app.core.errors import BusinessError

class KnowledgeRepository:
    def __init__(self, path, name):
        self.name = name
        self.lock = RLock()
        self.manifest = Path(path)/(name+'.active.json')
        self.client = chromadb.PersistentClient(path=path)
        active=json.loads(self.manifest.read_text(encoding='utf8')) if self.manifest.exists() else {'active':name,'versions':[name]}
        self.versions=active['versions']
        self.collection = self.client.get_or_create_collection(name=active['active'], metadata={'hnsw:space': 'cosine'})

    def publish(self,collection):
        versions=list(dict.fromkeys([*self.versions,collection.name]))
        temporary=self.manifest.with_name(self.manifest.name+'.'+uuid4().hex+'.tmp')
        try:
            with temporary.open('w',encoding='utf8') as output:
                json.dump({'active':collection.name,'versions':versions},output)
                output.flush();os.fsync(output.fileno())
            os.replace(temporary,self.manifest)
        finally:
            temporary.unlink(missing_ok=True)
        self.collection=collection;self.versions=versions

    def rebuild(self,documents,embeddings,metadatas,docs_hash='',build_id=''):
        with self.lock:
            name=self.name[:30]+'_'+uuid4().hex
            staging=self.client.create_collection(name=name,metadata={'hnsw:space':'cosine','docs_hash':docs_hash,'build_id':build_id})
            try:
                for start in range(0,len(documents),500):
                    chunk=documents[start:start+500]
                    staging.add(ids=[uuid4().hex for _ in chunk],documents=chunk,embeddings=embeddings[start:start+500],metadatas=metadatas[start:start+500])
                if staging.count()!=len(documents):
                    raise RuntimeError('Index validation failed')
                self.publish(staging)
            except BaseException:
                self.client.delete_collection(name)
                raise
            return name

    def version_list(self):
        return {'active':self.collection.name,'items':list(reversed(self.versions))}

    def append_version(self,documents,embeddings,metadatas):
        with self.lock:
            old=self.collection.get(include=['documents','embeddings','metadatas'])
            return self.rebuild(old['documents']+documents,list(old['embeddings'])+embeddings,
                [m or {'source':'manual'} for m in old['metadatas']]+metadatas,str(self.metadata.get('docs_hash','')))

    def delete_version(self,document_id):
        with self.lock:
            old=self.collection.get(include=['documents','embeddings','metadatas'])
            if document_id not in old['ids']:
                raise BusinessError(409,'知识版本已变化，请刷新片段列表后重试')
            keep=[i for i,key in enumerate(old['ids']) if key!=document_id]
            return self.rebuild([old['documents'][i] for i in keep],[old['embeddings'][i] for i in keep],
                [old['metadatas'][i] or {'source':'manual'} for i in keep],str(self.metadata.get('docs_hash','')))

    def rollback(self,name):
        with self.lock:
            if name not in self.versions:
                raise ValueError('Unknown knowledge version')
            self.publish(self.client.get_collection(name))

    @property
    def metadata(self):
        return self.collection.metadata or {}

    def count(self): return self.collection.count()
    def add(self, **kwargs):
        with self.lock:return self.collection.add(**kwargs)
    def query(self, **kwargs): return self.collection.query(**kwargs)
    def get(self, **kwargs): return self.collection.get(**kwargs)
    def delete(self, **kwargs):
        with self.lock:return self.collection.delete(**kwargs)
    def modify(self, **kwargs): return self.collection.modify(**kwargs)

    def reset(self):
        return self.rebuild([],[],[])

    def close(self):
        self.client.close()
