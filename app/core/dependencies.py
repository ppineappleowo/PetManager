"""
FastAPI 依赖注入 —— 通过 Depends() 向路由提供各项服务。

所有重资源（模型、数据库连接、RAG、Agent）在应用启动时创建并
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

from fastapi import Request

from app.core.config import Settings


def get_settings(request: Request) -> Settings:
    """从 app.state 获取 Settings（由 lifespan 注入）。"""
    return request.app.state.settings


def get_pet_agent_service(request: Request):
    """获取 PetAgentService（由 lifespan 注入）。

    Returns:
        PetAgentService 实例
    """
    return request.app.state.pet_agent_service
