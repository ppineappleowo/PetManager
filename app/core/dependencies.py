"""
FastAPI 依赖注入 —— 通过 Depends() 向路由提供各项服务。

所有重资源（模型、数据库连接、RAG、Agent、用户管理）在应用启动时创建并
挂载到 app.state，路由通过本模块提供的依赖函数获取。

使用示例:
    from fastapi import Depends
    from app.core.dependencies import get_settings, get_pet_agent_service

    @router.post("/chat")
    async def chat(
        request: ChatRequest,
        settings: Settings = Depends(get_settings),
        pet_service: PetAgentService = Depends(get_pet_agent_service),
    ):
        ...
"""

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings

security = HTTPBearer()


def get_settings(request: Request) -> Settings:
    """从 app.state 获取 Settings（由 lifespan 注入）。"""
    return request.app.state.settings


def get_pet_agent_service(request: Request):
    """获取 PetAgentService（由 lifespan 注入）。

    Returns:
        PetAgentService 实例
    """
    return request.app.state.pet_agent_service


def get_user_manager(request: Request):
    """获取 UserManager（由 lifespan 注入）。

    Returns:
        UserManager 实例
    """
    return request.app.state.user_manager


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """从 JWT Bearer Token 解析当前登录用户。

    Raises:
        HTTPException 401: Token 无效、过期或用户不存在。
    """
    settings: Settings = request.app.state.settings
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
            )
        user_id = int(user_id_str)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌已过期，请重新登录",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
        )

    user_manager = request.app.state.user_manager
    user = user_manager.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user
