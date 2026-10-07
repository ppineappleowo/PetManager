from fastapi import Depends, HTTPException, Request
from app.api.errors import ApiRouter
from starlette.concurrency import run_in_threadpool
from app.api.dependencies import get_current_user, get_rate_limiter
from app.services.rate_limits import enforce_limit
from app.services.media import upload_post_image
from app.api.v1.community.dependencies import store, image_response

router = ApiRouter()

@router.post('/media', status_code=201)
async def upload(request: Request, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    await run_in_threadpool(enforce_limit, limiter, [(f'community:upload:{user['id']}', 60)], 600)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, '每张图片最多 10 MB')
    return await run_in_threadpool(upload_post_image, db, user['id'], bytes(data), request.app.state.community_media)

@router.get('/media/{media_id}')
def own_image(media_id: str, request: Request, thumbnail: bool=False, user=Depends(get_current_user), db=Depends(store)):
    db.own_media(media_id, user['id'])
    return image_response(request, media_id, thumbnail)

@router.get('/posts/{post_id}/images/{media_id}')
def public_image(post_id: int, media_id: str, request: Request, thumbnail: bool=False, db=Depends(store)):
    if media_id not in db.get(post_id)['images']:
        raise HTTPException(404, '图片不可用')
    return image_response(request, media_id, thumbnail)
