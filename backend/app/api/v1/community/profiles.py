from fastapi import Depends, HTTPException, Query, Request, Response
from app.api.errors import ApiRouter
from starlette.concurrency import run_in_threadpool
from app.api.dependencies import get_current_user, get_rate_limiter, get_avatar_media
from app.services.rate_limits import enforce_limit
from app.services.media import replace_avatar, upload_avatar as save_avatar
from app.api.v1.community.dependencies import store, present, present_list, public_user, present_pet
from app.api.dependencies import get_user_manager

router = ApiRouter()

@router.get('/search/users')
def search_users(q:str=Query('',max_length=100),before:int|None=Query(None,ge=1),limit:int=Query(20,ge=1,le=50),users=Depends(get_user_manager)):
    return users.public_search(q.strip(),before,limit)

@router.get('/search/pets')
def search_pets(q:str=Query('',max_length=100),before:int|None=Query(None,ge=1),limit:int=Query(20,ge=1,le=50),db=Depends(store)):
    return db.search_pets(q.strip(),before,limit)

@router.get('/users/{user_id}')
def profile(user_id: int, request: Request, db=Depends(store)):
    user = public_user(user_id, request)
    data = present({'user_id': user_id}, request)['author']
    data['bio'] = '' if user.get('profile_hidden') else user['bio']
    data['post_count'] = db.listing(author=user_id, limit=1)['total']
    data['pets'] = [present_pet(pet) for pet in db.pets(user_id) if not pet.get('hidden')]
    return data

@router.get('/users/{user_id}/posts')
def profile_posts(user_id: int, request: Request, before: int | None=Query(None, ge=1), limit: int=Query(24, ge=1, le=50), db=Depends(store)):
    public_user(user_id, request)
    return present_list(db.listing(author=user_id, before=before, limit=limit), request)

@router.get('/users/{user_id}/avatar/{avatar_id}')
def avatar(user_id: int, avatar_id: str, request: Request, media=Depends(get_avatar_media)):
    user = public_user(user_id, request)
    if user.get('avatar_hidden') or not avatar_id or avatar_id != user['avatar_id']:
        raise HTTPException(404, '头像不可用')
    return Response(media.get(avatar_id, True), media_type='image/webp', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

@router.put('/me/avatar')
async def upload_avatar(request: Request, user=Depends(get_current_user), limiter=Depends(get_rate_limiter), media=Depends(get_avatar_media)):
    await run_in_threadpool(enforce_limit, limiter, [(f'community:avatar:{user['id']}', 10)], 600)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(413, '头像最多 5 MB')
    return await run_in_threadpool(save_avatar, request.app.state.user_manager, user['id'], bytes(data), media)

@router.delete('/me/avatar')
def remove_avatar(request: Request, user=Depends(get_current_user), media=Depends(get_avatar_media)):
    return replace_avatar(request.app.state.user_manager, user['id'], '', media)
