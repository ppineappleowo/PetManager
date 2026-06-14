"""
AI 宠物管家 —— FastAPI 应用入口

使用 lifespan 管理所有重资源的创建与销毁，通过 app.state 向路由层
提供依赖注入，消除模块级全局状态。
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# 尽早加载 .env 到 os.environ，确保第三方库（LangSmith 等）能读取
load_dotenv()

# fmt: off
# isort: off
# ↓ 以下导入必须在 load_dotenv() 之后，确保环境变量已就绪
import dashscope  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.v1 import chat, oss, auth  # noqa: E402
from app.common.logger import setup_logging, logger  # noqa: E402
from app.common.rag_manager import RAGManager  # noqa: E402
from app.common.user_manager import UserManager  # noqa: E402
from app.agents.demo import PetAgentService  # noqa: E402
from app.core.config import get_settings, reset_settings  # noqa: E402
# fmt: on
# isort: on


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用启动/关闭时的资源初始化和释放。

    启动时:
    1. 加载配置
    2. 配置 DashScope API key
    3. 创建 RAG 知识库管理器
    4. 创建 PetAgentService（含模型、Agent、数据库、知识库加载）

    关闭时:
    1. 释放 PetAgentService 持有的数据库连接等资源
    2. 清理配置缓存
    """
    # ═══════ 启动 ═══════
    logger.info("=" * 50)
    logger.info("AI 宠物管家启动中...")

    # 1. 加载配置
    settings = get_settings()
    logger.info(f"配置已加载，LLM: {settings.llm_model}")

    # 2. 配置 DashScope（需要在 RAGManager 之前）
    _setup_dashscope(settings)

    # 3. 创建 RAG 知识库管理器
    rag_manager = RAGManager(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.chroma_collection_name,
        embedding_model=settings.embedding_model,
        embedding_dim=settings.embedding_dim,
        embedding_batch_size=settings.embedding_batch_size,
        rerank_model=settings.rerank_model,
    )

    # 4. 创建用户管理器
    user_manager = UserManager(db_path=settings.users_db_path)

    # 5. 创建 Agent 服务（含知识库加载）
    pet_agent_service = PetAgentService(
        settings=settings,
        rag_manager=rag_manager,
    )

    # 6. 挂载到 app.state 供路由层依赖注入
    app.state.settings = settings
    app.state.user_manager = user_manager
    app.state.pet_agent_service = pet_agent_service

    logger.info("AI 宠物管家启动完成！")
    logger.info("=" * 50)

    yield  # ← 应用运行中

    # ═══════ 关闭 ═══════
    logger.info("AI 宠物管家正在关闭...")
    try:
        pet_agent_service.close()
    except Exception as e:
        logger.warning(f"关闭 PetAgentService 时出错: {e}")
    try:
        user_manager.close()
    except Exception as e:
        logger.warning(f"关闭 UserManager 时出错: {e}")
    reset_settings()
    logger.info("AI 宠物管家已关闭")


def _setup_dashscope(settings):
    """配置 DashScope SDK 的 API key。

    Raises:
        RuntimeError: API key 未设置时。
    """
    api_key = settings.dashscope_api_key
    if not api_key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY 未设置！"
            "请在 .env 文件中配置或设置环境变量"
        )
    dashscope.api_key = api_key
    logger.info(f"DashScope API key 已配置 ({api_key[:10]}...)")


# ==================== 应用实例 ====================

# 初始化日志
setup_logging()

app = FastAPI(
    title="AI Pet Manager API",
    description="AI 宠物管家",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS 跨域配置 ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 挂载 API 路由 ──
app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
app.include_router(oss.router, prefix="/api/v1", tags=["申请上传签名url"])

# ── 挂载前端静态资源 ──
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


# ── 前端 SPA fallback 路由 ──
@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend(path: str):
    """处理非 API 请求：静态文件优先，否则回退到 index.html（SPA）。"""
    if path.startswith("api/"):
        return JSONResponse({"error": "Not Found"}, status_code=404)

    file_path = os.path.join(static_dir, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {"message": "你的AI宠物管家上线了~", "status": "ok"}


# ==================== 直接启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
    )
