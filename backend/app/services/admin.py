from app.core.errors import BusinessError
from anyio import to_thread

def history_service(state):
    return getattr(state,'chat_history',None) or state.pet_agent_service

def all_threads(state):
    service = history_service(state)
    if service is None:
        return []
    result = []
    for user in state.user_manager.list_users():
        for thread in service.list_threads(str(user['id'])):
            result.append({**thread, 'user_id': user['id'], 'username': user['username'],
                           'running': bool(state.chat_streams and state.chat_streams.busy(str(user['id']), thread['thread_id']))})
    return result

async def overview(state):
    users = await to_thread.run_sync(state.user_manager.list_users)
    threads = await to_thread.run_sync(all_threads,state)
    settings = state.settings
    return {'users': len(users), 'admins': sum(u['role'] == 'admin' for u in users),
            'disabled': sum(bool(u['disabled']) for u in users), 'threads': len(threads),
            'messages': sum(t['message_count'] for t in threads), 'active': len(state.chat_streams.active) if state.chat_streams else 0,
            'ai_status': getattr(state, 'ai_status', 'ready'),
            'knowledge': state.pet_agent_service.rag_get_stats() if state.pet_agent_service else {'document_count': None},
            'config': {name: getattr(settings, name) for name in (
                'llm_model', 'embedding_model', 'rerank_model', 'chat_timeout_seconds',
                'login_max_attempts', 'login_ip_max_attempts', 'login_window_seconds')}}

async def users(state, q, offset, limit):
    from anyio import to_thread
    return await to_thread.run_sync(lambda:state.user_manager.search(q,offset,limit))

async def update_user(user_id, body, state, actor):
    await to_thread.run_sync(lambda:state.user_manager.admin_update(user_id, actor['id'], **body.model_dump()))
    if (body.disabled or body.revoke) and state.chat_streams:
        streams = state.chat_streams
        for key in list(streams.active):
            if key[0] == str(user_id):
                await streams.stop(*key)
    return {'success': True}

async def threads(state, q, offset, limit):
    rows = [t for t in await to_thread.run_sync(all_threads,state) if q.lower() in (t['username'] + ' ' + t['title']).lower()]
    return {'items': rows[offset:offset + limit], 'total': len(rows)}

async def messages(user_id, thread_id, state):
    return {'messages': await to_thread.run_sync(history_service(state).get_messages,thread_id,str(user_id))}

async def delete_messages(user_id, thread_id, state):
    if state.chat_streams and state.chat_streams.busy(str(user_id), thread_id):
        raise BusinessError(409, '请先停止该会话的生成')
    await to_thread.run_sync(history_service(state).clear_messages,thread_id,str(user_id))
    return {'success': True}

async def stop(user_id, thread_id, state):
    streams = state.chat_streams
    if streams is None:return {'success':True}
    for key, run in list(streams.active.items()):
        if key[0] == str(user_id) and run['thread_id'] == thread_id:
            await streams.stop(*key)
    return {'success': True}

def knowledge(state, offset, limit):
    return state.pet_agent_service.rag_manager.list_documents(offset, limit)

def add_knowledge(body, state,actor_id=0,rag=None):
    if not body.text.strip():
        raise BusinessError(422, '知识内容不能为空')
    jobs=getattr(state,'knowledge_jobs',None)
    if jobs is not None:
        from uuid import uuid4
        job=jobs.create(actor_id,'手动知识_'+uuid4().hex[:8],body.text.strip())
        jobs.run(job['id'],rag or state.pet_agent_service.rag_manager)
        return {'added':1,'job_id':job['id']}
    return {'added': state.pet_agent_service.rag_add_documents([body.text.strip()])}

def delete_knowledge(document_id, state):
    return state.pet_agent_service.rag_manager.delete_document(document_id)
