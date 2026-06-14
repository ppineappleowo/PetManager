"""对话 & RAG 管理 API —— 通过 FastAPI 依赖注入获取服务实例。"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, RAGAddRequest
from app.core.dependencies import get_pet_agent_service, get_current_user


router = APIRouter()


def _uid(user: dict) -> str:
    """从 current_user 提取 user_id 字符串。"""
    return str(user["id"])


# ==================== 对话接口 ====================

@router.post("/chat/stream")
async def chat_endpoint(
    request: ChatRequest,
    pet_service=Depends(get_pet_agent_service),
    current_user=Depends(get_current_user),
):
    """流式对话 —— Server-Sent Events (SSE) 格式"""
    return StreamingResponse(
        pet_service.consult(
            prompt=request.message,
            image=request.image_url,
            thread_id=request.thread_id,
            user_id=_uid(current_user),
        ),
        media_type="text/event-stream",
    )


@router.get("/chat/messages")
async def get_chat_messages(
    thread_id: str = Query(..., description="会话 ID"),
    pet_service=Depends(get_pet_agent_service),
    current_user=Depends(get_current_user),
):
    """获取会话历史消息"""
    messages = pet_service.get_messages(thread_id, user_id=_uid(current_user))
    return {"messages": messages}


@router.delete("/chat/messages")
async def clear_chat_messages(
    thread_id: str = Query(..., description="会话 ID"),
    pet_service=Depends(get_pet_agent_service),
    current_user=Depends(get_current_user),
):
    """清空会话历史"""
    pet_service.clear_messages(thread_id, user_id=_uid(current_user))
    return {"success": True}


@router.get("/chat/threads")
async def get_thread_list(
    pet_service=Depends(get_pet_agent_service),
    current_user=Depends(get_current_user),
):
    """获取所有会话列表"""
    threads = pet_service.list_threads(user_id=_uid(current_user))
    return {"threads": threads}


# ==================== RAG 知识库管理接口 ====================

@router.post("/rag/documents")
async def add_rag_documents(
    request: RAGAddRequest,
    pet_service=Depends(get_pet_agent_service),
):
    """向 RAG 知识库添加文档"""
    count = pet_service.rag_add_documents(request.documents)
    return {"success": True, "added": count}


@router.delete("/rag/documents")
async def clear_rag(
    pet_service=Depends(get_pet_agent_service),
):
    """清空并重置 RAG 知识库"""
    pet_service.rag_clear()
    stats = pet_service.rag_get_stats()
    return {"success": True, "document_count": stats["document_count"]}


@router.get("/rag/stats")
async def get_rag_stats(
    pet_service=Depends(get_pet_agent_service),
):
    """获取 RAG 知识库统计信息"""
    return pet_service.rag_get_stats()
