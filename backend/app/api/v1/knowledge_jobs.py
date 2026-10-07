from fastapi import Depends,Query,Request
from pydantic import BaseModel,Field,field_validator
from app.api.errors import ApiRouter
from app.api.dependencies import get_admin_user,get_knowledge_manager

router=ApiRouter(prefix='/admin',dependencies=[Depends(get_admin_user)])


class SourceInput(BaseModel):
    source:str=Field(min_length=1,max_length=100)
    text:str=Field(min_length=1,max_length=1000000)

    @field_validator('source','text')
    @classmethod
    def nonempty(cls,value):
        if not value.strip():raise ValueError('内容不能为空')
        return value.strip()


@router.get('/knowledge-jobs')
def jobs(request:Request,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50)):
    return request.app.state.knowledge_jobs.listing(offset,limit)


@router.post('/knowledge-jobs',status_code=201)
def create(body:SourceInput,request:Request,actor=Depends(get_admin_user)):
    return request.app.state.knowledge_jobs.create(actor['id'],body.source,body.text)


@router.post('/knowledge-jobs/{job_id}/run')
def run(job_id:str,request:Request,rag=Depends(get_knowledge_manager)):
    return request.app.state.knowledge_jobs.run(job_id,rag)


@router.get('/knowledge-versions')
def versions(rag=Depends(get_knowledge_manager)):
    return rag.repository.version_list()


class VersionInput(BaseModel):
    version:str=Field(min_length=1,max_length=100)


@router.post('/knowledge-versions/rollback')
def rollback(body:VersionInput,rag=Depends(get_knowledge_manager)):
    from fastapi import HTTPException
    try:rag.repository.rollback(body.version)
    except ValueError:raise HTTPException(404,'知识版本不存在') from None
    return {'success':True}
