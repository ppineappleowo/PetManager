from contextvars import ContextVar
from time import perf_counter
from uuid import UUID,uuid4
from app.core.logging import logger

request_metrics=ContextVar('request_metrics',default=None)


class RequestMetricsMiddleware:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]))
        try:request_id=str(UUID(headers.get(b'x-request-id',b'').decode('ascii')))
        except (ValueError,UnicodeError):request_id=str(uuid4())
        stats={'sql_count':0,'sql_ms':0.0};token=request_metrics.set(stats)
        started=perf_counter();status=500
        async def output(message):
            nonlocal status
            if message['type']=='http.response.start':
                status=message['status']
                message['headers']=[*message.get('headers',[]),(b'x-request-id',request_id.encode())]
            await send(message)
        try:await self.app(scope,receive,output)
        finally:
            logger.info('request_id=%s method=%s path=%s status=%s elapsed_ms=%.1f sql_count=%s sql_ms=%.1f',
                request_id,scope['method'],scope['path'],status,(perf_counter()-started)*1000,stats['sql_count'],stats['sql_ms'])
            request_metrics.reset(token)
