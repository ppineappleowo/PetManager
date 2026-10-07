"""单 worker 的可取消 SSE 任务，持久化终态，重复请求回放已完成答案。"""
import asyncio
import json
from anyio import CancelScope,to_thread
from contextlib import suppress
from app.core.errors import BusinessError
from app.core.logging import logger


def sse(event, data):
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


class ChatStreams:
    def __init__(self, service, timeout=180):
        self.service = service
        self.store = service.turn_store
        self.timeout = timeout
        self.active = {}
        self.start_lock=asyncio.Lock()

    def busy(self, user_id, thread_id):
        return any(key[0] == user_id and run['thread_id'] == thread_id for key, run in self.active.items())

    def start(self, user_id, request, context=None):
        request_id = str(request.request_id)
        key = (user_id, request_id)
        if self.busy(user_id, request.thread_id):
            raise BusinessError(409, '此会话仍在生成，请先停止或稍后重试')
        row = self.store.begin(user_id, request.thread_id, request_id, request.message, request.image_url,context)
        return self._start_run(user_id,request,context,row)

    async def start_async(self,user_id,request,context=None):
        async with self.start_lock:
            if self.busy(user_id,request.thread_id):
                raise BusinessError(409,'此会话仍在生成，请先停止或稍后重试')
            row=await to_thread.run_sync(lambda:self.store.begin(user_id,request.thread_id,str(request.request_id),request.message,request.image_url,context))
            return self._start_run(user_id,request,context,row)

    def _start_run(self,user_id,request,context,row):
        request_id=str(request.request_id)
        key=(user_id,request_id)
        queue = asyncio.Queue()
        run = {'thread_id': request.thread_id, 'answer': '', 'queue': queue, 'status': 'running', 'task': None,'context':context or {}}
        if row['status'] == 'completed':
            queue.put_nowait(('sources', {'items': json.loads(row['sources'])}))
            queue.put_nowait(('delta', {'text': row['answer']}))
            queue.put_nowait(('done', {'status': 'completed', 'request_id': request_id}))
            run['status'] = 'completed'
            return key, run
        self.active[key] = run
        run['task'] = asyncio.create_task(self._produce(key, run, request))
        return key, run

    async def _produce(self, key, run, request):
        status, error = 'completed', ''
        try:
            async with asyncio.timeout(self.timeout):
                args = (request.message, request.image_url, request.thread_id, key[0])
                if run['context']:
                    args += (run['context'],)
                async for event in self.service.consult(*args):
                    if event['event'] == 'delta':
                        run['answer'] += event['data']['text']
                    if event['event'] == 'sources':
                        await to_thread.run_sync(self.store.sources,*key,event['data']['items'])
                    await run['queue'].put((event['event'], event['data']))
                if not run['answer'].strip():
                    raise ValueError('Empty model response')
        except asyncio.CancelledError:
            status = 'cancelled'
        except TimeoutError:
            status, error = 'failed', '生成超时，请重试'
        except Exception:
            logger.warning('生成失败 request_id=%s', key[1])
            status, error = 'failed', '生成失败，请稍后重试'
        finally:
            run['status'] = status
            with CancelScope(shield=True):
                await to_thread.run_sync(self.store.finish,*key,status,run['answer'],error)
            self.active.pop(key, None)
        # 终态先持久化再发送。停止时清空队列，避免回放停止前积压的片段。
        if status == 'cancelled':
            while not run['queue'].empty():
                run['queue'].get_nowait()
        if error:
            await run['queue'].put(('error', {'message': error, 'retryable': True}))
        await run['queue'].put(('done', {'status': status, 'request_id': key[1]}))

    async def stop(self, user_id, request_id):
        key = (user_id, request_id)
        run = self.active.get(key)
        if run:
            run['task'].cancel()
            with suppress(asyncio.CancelledError):
                await run['task']
            # task 在首次调度前被取消时，coroutine 的 finally 不会执行。
            if key in self.active:
                await to_thread.run_sync(self.store.finish,*key,'cancelled',run['answer'])
                self.active.pop(key, None)
                run['status'] = 'cancelled'
                run['queue'].put_nowait(('done', {'status': 'cancelled', 'request_id': request_id}))
        row = await to_thread.run_sync(self.store.get,user_id,request_id)
        if not row:
            raise BusinessError(404, '请求不存在')
        return {'status': row['status'], 'request_id': request_id}

    async def stream(self, key, run):
        try:
            yield sse('status', {'stage': 'thinking', 'message': '正在理解问题', 'request_id': key[1]})
            while True:
                try:
                    event, data = await asyncio.wait_for(run['queue'].get(), 15)
                except TimeoutError:
                    yield ': heartbeat\n\n'
                    continue
                yield sse(event, data)
                if event == 'done':
                    break
        finally:
            if key in self.active:
                # Starlette 在取消作用域中关闭响应；屏蔽该作用域以完成落库。
                with CancelScope(shield=True):
                    await self.stop(*key)

    async def close(self):
        for key in list(self.active):
            await self.stop(*key)
