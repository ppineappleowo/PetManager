from contextvars import ContextVar
from hashlib import sha256
from urllib.parse import urlparse

evidence = ContextVar('retrieval_evidence',default=None)


def collect_local(doc):
    items=evidence.get()
    if items is None:
        return
    meta=doc.get('metadata') or {}
    item={'id':meta.get('chunk_id') or sha256(doc['content'].encode()).hexdigest()[:16],
        'source':str(meta.get('source','本地知识资料'))[:200],
        'version':str(meta.get('version','legacy')),'excerpt':doc['content'][:500],'type':'knowledge'}
    if not any(x['id']==item['id'] for x in items):
        items.append(item)


def collect_web(result):
    items=evidence.get()
    if items is None or not isinstance(result,dict):
        return
    for row in result.get('results',[])[:5]:
        url=row.get('url','')
        if urlparse(url).scheme not in ('https','http'):
            continue
        if not any(x.get('url')==url for x in items):
            items.append({'id':sha256(url.encode()).hexdigest()[:16],'type':'web','source':str(row.get('title','网络资料'))[:200],
                'url':url,'excerpt':str(row.get('content',''))[:500],'version':''})
