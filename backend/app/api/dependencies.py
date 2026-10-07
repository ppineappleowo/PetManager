from app.services.authentication import authenticate_token
from app.core.errors import BusinessError
"""
FastAPI 依赖注入 —— 通过 Depends() 向路由提供各项服务。

所有重资源（模型、数据库连接、RAG、Agent、用户管理）在应用启动时创建并
挂载到 app.state，路由通过本模块提供的依赖函数获取。

使用示例:
    from fastapi import Depends
    from app.api.dependencies import get_settings, get_pet_agent_service

    @router.post("/chat")
    async def chat(
        request: ChatRequest,
        settings: Settings = Depends(get_settings),
        pet_service: PetAgentService = Depends(get_pet_agent_service),
    ):
        ...
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.rate_limit import RateLimiter

security = HTTPBearer(auto_error=False)


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def get_redis_service(request: Request):
    return request.app.state.redis_service


def get_settings(request: Request) -> Settings:
    """从 app.state 获取 Settings（由 lifespan 注入）。"""
    return request.app.state.settings


def get_pet_agent_service(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """获取 PetAgentService（由 lifespan 注入）。

    Returns:
        PetAgentService 实例
    """
    get_current_user(request, credentials)
    state = request.app.state
    if getattr(state, 'pet_agent_service', None) is None:
        initializer = getattr(state, 'initialize_ai', None)
        if initializer:
            initializer()
    if getattr(state, 'pet_agent_service', None) is None:
        raise HTTPException(503, 'AI 助手暂不可用，请稍后重试；社区功能正常')
    return state.pet_agent_service


def get_user_manager(request: Request):
    """获取 UserService（由 lifespan 注入）。

    Returns:
        UserService 实例
    """
    return request.app.state.user_manager


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """从 JWT Bearer Token 解析当前登录用户。

    Raises:
        HTTPException 401: Token 无效、过期或用户不存在。
    """
    if credentials is None:
        raise HTTPException(401, '请先登录', headers={'WWW-Authenticate': 'Bearer'})
    try:
        return authenticate_token(request.app.state.user_manager, request.app.state.settings, credentials.credentials)
    except BusinessError as error:
        raise HTTPException(error.status_code, error.detail, error.headers) from error


def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user

def get_avatar_media(settings=Depends(get_settings)):
    from app.infrastructure.storage.avatar import AvatarMedia
    return AvatarMedia(settings)

def get_chat_history(request: Request,current_user=Depends(get_current_user)):
    service=getattr(request.app.state,'chat_history',None)
    return service if service is not None else request.app.state.pet_agent_service

def get_knowledge_manager(request: Request,actor=Depends(get_admin_user)):
    initializer=getattr(request.app.state,'initialize_knowledge',None)
    if initializer:
        try:return initializer()
        except Exception:raise HTTPException(503,'知识检索服务暂不可用，可稍后重试') from None
    return request.app.state.pet_agent_service.rag_manager
