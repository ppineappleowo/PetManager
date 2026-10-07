"""业务错误到 HTTP 的统一边界，独立 router 测试也沿用同一映射。"""
from fastapi import APIRouter, HTTPException
from fastapi.routing import APIRoute
from app.core.errors import BusinessError


class BusinessRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request):
            try:
                return await handler(request)
            except BusinessError as error:
                raise HTTPException(error.status_code, error.detail, error.headers) from error

        return handle


class ApiRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('route_class', BusinessRoute)
        super().__init__(*args, **kwargs)
