from fastapi import APIRouter
from app.models.schemas import ChatRequest, RAGAddRequest
from app.agents.demo import pet_consult, get_messages, clear_messages, list_threads,rag_add_documents, rag_clear, rag_get_stats
from fastapi.responses import StreamingResponse

router = APIRouter()


# ==================== 对话 ====================

@router.post("/chat/stream")
async def chat_endpoint(request: ChatRequest):
    """流式对话"""
    return StreamingResponse(
        pet_consult(request.message, request.image_url, request.thread_id),
        media_type="text/event-stream"
    )


@router.get("/chat/messages")
async def get_chat_messages(thread_id: str):
    """获取历史消息"""
    messages = get_messages(thread_id)
    return {"messages": messages}


@router.delete("/chat/messages")
async def clear_chat_messages(thread_id: str):
    """清空历史消息"""
    clear_messages(thread_id)
    return {"success": True}


@router.get("/chat/threads")
async def get_thread_list():
    """获取所有会话列表"""
    threads = list_threads()
    return {"threads": threads}


# ==================== RAG 知识库管理 ====================

@router.post("/rag/documents")
async def add_rag_documents(request: RAGAddRequest):
    """向 RAG 知识库添加文档"""
    count = rag_add_documents(request.documents)
    return {"success": True, "added": count}


@router.delete("/rag/documents")
async def clear_rag():
    """清空并重置 RAG 知识库"""
    rag_clear()
    stats = rag_get_stats()
    return {"success": True, "document_count": stats["document_count"]}


@router.get("/rag/stats")
async def get_rag_stats():
    """获取 RAG 知识库统计信息"""
    return rag_get_stats()
