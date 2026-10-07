"""百宠集 API。社区独立启动；AI 首次使用时在工作线程中初始化。"""
from contextlib import asynccontextmanager, ExitStack
from pathlib import Path
from threading import Lock
from time import monotonic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import chat, oss, auth, admin, community
from app.api.v1 import governance,ai_feedback,knowledge_jobs
from app.services.ai.history import ConversationHistory
from app.services.ai.knowledge_jobs import KnowledgeJobs
from app.core.logging import setup_logging, logger
from app.services.users import UserService
from app.services.community.posts import CommunityService
from app.services.ai.streams import ChatStreams
from app.core.config import get_settings, reset_settings
from app.api.dependencies import get_redis_service
from app.database.redis import RedisService, RedisUnavailable
from app.database.redis_rate_limiter import RedisRateLimiter
from app.infrastructure.storage.community import CommunityMedia
from app.database.setup import initialize_database
from app.core.observability import RequestMetricsMiddleware


def RAGManager(**kwargs):
    from app.services.ai.retrieval import RAGManager as Factory
    return Factory(**kwargs)


def PetAgentService(**kwargs):
    from app.services.ai.agent import PetAgentService as Factory
    return Factory(**kwargs)


def _setup_dashscope(settings):
    import dashscope
    if not settings.dashscope_api_key:
        raise RuntimeError('DASHSCOPE_API_KEY 未配置')
    dashscope.api_key = settings.dashscope_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    with ExitStack() as resources:
        resources.callback(reset_settings)
        settings = get_settings()
        database_url = settings.database_url.get_secret_value()
        initialize_database(database_url)
        redis_service = RedisService.from_settings(settings)
        resources.callback(redis_service.close)
        try:
            redis_service.ping()
        except RedisUnavailable:
            logger.warning('Redis 暂不可用；登录与社区浏览继续提供服务，依赖 Redis 的操作暂不可用')
        state = app.state
        state.settings = settings
        state.redis_service = redis_service
        state.rate_limiter = RedisRateLimiter(redis_service.client, settings.redis_namespace)
        state.user_manager = UserService(db_path=database_url)
        resources.callback(state.user_manager.close)
        state.community_store = CommunityService(database_url)
        resources.callback(state.community_store.close)
        state.community_media = CommunityMedia(settings)
        state.chat_history = ConversationHistory(database_url)
        state.knowledge_jobs = KnowledgeJobs(database_url,settings.rag_chunk_size,settings.rag_chunk_overlap)
        resources.callback(state.chat_history.close)
        resources.callback(state.knowledge_jobs.close)
        state.pet_agent_service = None
        state.chat_streams = None
        state.ai_status = 'idle'
        ai_lock = Lock()
        knowledge_lock=Lock()
        state.rag_manager=None
        retry_at = 0

        def initialize_knowledge():
            with knowledge_lock:
                if state.rag_manager is None:
                    if settings.dashscope_api_key:
                        _setup_dashscope(settings)
                    rag=RAGManager(persist_dir=settings.chroma_persist_dir,collection_name=settings.chroma_collection_name,
                        embedding_model=settings.embedding_model,embedding_dim=settings.embedding_dim,
                        embedding_batch_size=settings.embedding_batch_size,rerank_model=settings.rerank_model)
                    resources.callback(rag.repository.close)
                    state.rag_manager=rag
                return state.rag_manager
        state.initialize_knowledge=initialize_knowledge

        def initialize_ai():
            nonlocal retry_at
            with ai_lock:
                if state.pet_agent_service is not None or monotonic() < retry_at:
                    return
                state.ai_status = 'loading'
                service = None
                try:
                    _setup_dashscope(settings)
                    rag = initialize_knowledge()
                    service = PetAgentService(settings=settings, rag_manager=rag,knowledge_jobs=state.knowledge_jobs)
                    state.chat_streams = ChatStreams(service, settings.chat_timeout_seconds)
                    state.pet_agent_service = service
                    state.ai_status = 'ready'
                except Exception as error:
                    if service is not None:
                        service.close()
                    state.ai_status = 'unavailable'
                    retry_at = monotonic() + 30
                    logger.warning('AI 初始化失败（%s），社区继续可用', type(error).__name__)

        state.initialize_ai = initialize_ai
        logger.info('百宠集社区已启动；AI 将在首次使用时初始化')
        try:
            yield
        finally:
            if state.chat_streams is not None:
                await state.chat_streams.close()
            if state.pet_agent_service is not None:
                state.pet_agent_service.close()


setup_logging()
def create_app():
    instance=FastAPI(title='百宠集 API',version='0.3.0',lifespan=lifespan)
    instance.add_middleware(RequestMetricsMiddleware)
    instance.add_middleware(CORSMiddleware,allow_origins=get_settings().cors_origins,
        allow_credentials=True,allow_methods=['*'],allow_headers=['*'],expose_headers=['Retry-After','X-Request-ID'])
    for module in (auth,admin,chat,oss,community,governance,ai_feedback,knowledge_jobs):
        instance.include_router(module.router,prefix='/api/v1')
    for path,endpoint in [('/',service_status),('/health/ai',ai_health),('/health/redis',redis_health),('/health/database',database_health)]:
        instance.add_api_route(path,endpoint,methods=['GET'])
    return instance


def service_status():
    return {'message': '百宠集 · 每一种宠爱，都有同好。', 'status': 'ok'}


def ai_health(request: Request):
    return {'status': getattr(request.app.state, 'ai_status', 'idle')}


def redis_health(service=Depends(get_redis_service)):
    try:
        service.ping()
    except RedisUnavailable:
        raise HTTPException(503, 'Redis unavailable') from None
    return {'redis': 'ok'}


def database_health(request: Request):
    try:
        request.app.state.user_manager.health()
    except Exception:
        raise HTTPException(503, 'PostgreSQL unavailable') from None
    return {'database': 'postgresql', 'status': 'ok'}


app=create_app()

if __name__ == '__main__':
    import uvicorn
    settings = get_settings()
    uvicorn.run('app.main:app', host=settings.server_host, port=settings.server_port, reload=True)
