from fastapi import Depends, Query, Request
from app.api.errors import ApiRouter
from app.api.dependencies import get_admin_user, get_chat_history, get_knowledge_manager
from app.api.schemas.admin import UserUpdate, KnowledgeInput
from app.services import admin as admin_service

router = ApiRouter(prefix='/admin', dependencies=[Depends(get_admin_user)])

@router.get('/overview')
async def overview(request: Request):
    return await admin_service.overview(request.app.state)

@router.get('/users')
async def users(request: Request, q: str = '', offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return await admin_service.users(request.app.state, q, offset, limit)

@router.patch('/users/{user_id}')
async def update_user(user_id: int, body: UserUpdate, request: Request, actor=Depends(get_admin_user)):
    return await admin_service.update_user(user_id, body, request.app.state, actor)

@router.get('/threads')
async def threads(request: Request, q: str = '', offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), service=Depends(get_chat_history)):
    return await admin_service.threads(request.app.state, q, offset, limit)

@router.get('/users/{user_id}/messages')
async def messages(user_id: int, thread_id: str, request: Request, service=Depends(get_chat_history)):
    return await admin_service.messages(user_id, thread_id, request.app.state)

@router.delete('/users/{user_id}/messages')
async def delete_messages(user_id: int, thread_id: str, request: Request, service=Depends(get_chat_history)):
    return await admin_service.delete_messages(user_id, thread_id, request.app.state)

@router.post('/users/{user_id}/stop')
async def stop(user_id: int, thread_id: str, request: Request, service=Depends(get_chat_history)):
    return await admin_service.stop(user_id, thread_id, request.app.state)

@router.get('/knowledge')
def knowledge(request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), rag=Depends(get_knowledge_manager)):
    return rag.list_documents(offset, limit)

@router.post('/knowledge')
def add_knowledge(body: KnowledgeInput, request: Request, rag=Depends(get_knowledge_manager),actor=Depends(get_admin_user)):
    return admin_service.add_knowledge(body, request.app.state,actor['id'],rag)

@router.delete('/knowledge/{document_id}')
def delete_knowledge(document_id: str, request: Request, rag=Depends(get_knowledge_manager)):
    return rag.delete_document(document_id)
