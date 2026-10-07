from app.api.errors import ApiRouter
"""对话 & RAG 管理 API —— 通过 FastAPI 依赖注入获取服务实例。"""

from fastapi import Depends, Query, Request, HTTPException
from uuid import UUID
from fastapi.responses import StreamingResponse

from app.api.schemas.auth_chat import ChatRequest, RAGAddRequest
from app.api.dependencies import get_pet_agent_service, get_current_user, get_admin_user, get_chat_history


router = ApiRouter()


def get_streams(request: Request, service=Depends(get_pet_agent_service)):
    return request.app.state.chat_streams


def _uid(user: dict) -> str:
    """从 current_user 提取 user_id 字符串。"""
    return str(user["id"])


# ==================== 对话接口 ====================

@router.post("/chat/stream")
async def chat_endpoint(
    request: ChatRequest,
    http_request: Request,
    streams=Depends(get_streams),
    current_user=Depends(get_current_user),
):
    """流式对话 —— Server-Sent Events (SSE) 格式"""
    context = {}
    if request.pet_id:
        from starlette.concurrency import run_in_threadpool
        pet = await run_in_threadpool(http_request.app.state.community_store.pet,request.pet_id,current_user['id'])
        context = {key:pet[key] for key in ('id','name','species','breed','sex','birthday','bio','version')}
    key, run = await streams.start_async(_uid(current_user), request, context)
    return StreamingResponse(streams.stream(key, run), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/chat/requests/{request_id}/stop")
async def stop_generation(request_id: UUID, streams=Depends(get_streams), current_user=Depends(get_current_user)):
    return await streams.stop(_uid(current_user), str(request_id))


@router.get("/chat/messages")
def get_chat_messages(
    thread_id: str = Query(..., description="会话 ID"),
    pet_service=Depends(get_chat_history),
    current_user=Depends(get_current_user),
):
    """获取会话历史消息"""
    messages = pet_service.get_messages(thread_id, user_id=_uid(current_user))
    return {"messages": messages}


@router.delete("/chat/messages")
def clear_chat_messages(
    thread_id: str = Query(..., description="会话 ID"),
    pet_service=Depends(get_chat_history),
    current_user=Depends(get_current_user),
    streams_request: Request = None,
):
    """清空会话历史"""
    streams = getattr(streams_request.app.state,'chat_streams',None)
    if streams and streams.busy(_uid(current_user), thread_id):
        raise HTTPException(409, "请先停止此会话的生成")
    pet_service.clear_messages(thread_id, user_id=_uid(current_user))
    return {"success": True}


@router.get("/chat/threads")
def get_thread_list(
    pet_service=Depends(get_chat_history),
    current_user=Depends(get_current_user),
):
    """获取所有会话列表"""
    threads = pet_service.list_threads(user_id=_uid(current_user))
    return {"threads": threads}


# ==================== RAG 知识库管理接口 ====================

@router.post("/rag/documents", dependencies=[Depends(get_admin_user)])
def add_rag_documents(
    request: RAGAddRequest,
    pet_service=Depends(get_pet_agent_service),
):
    """向 RAG 知识库添加文档"""
    count = pet_service.rag_add_documents(request.documents)
    return {"success": True, "added": count}


@router.delete("/rag/documents", dependencies=[Depends(get_admin_user)])
def clear_rag(
    pet_service=Depends(get_pet_agent_service),
):
    """清空并重置 RAG 知识库"""
    pet_service.rag_clear()
    stats = pet_service.rag_get_stats()
    return {"success": True, "document_count": stats["document_count"]}


@router.get("/rag/stats", dependencies=[Depends(get_admin_user)])
def get_rag_stats(
    pet_service=Depends(get_pet_agent_service),
):
    """获取 RAG 知识库统计信息"""
    return pet_service.rag_get_stats()
