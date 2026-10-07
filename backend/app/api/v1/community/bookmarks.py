from fastapi import Depends, Query, Request
from app.api.errors import ApiRouter
from app.api.dependencies import get_current_user, get_rate_limiter
from app.api.v1.community.dependencies import store, present_list
from app.services.rate_limits import enforce_limit

router = ApiRouter()


@router.get('/me/bookmarks')
def listing(request: Request, before: int | None=Query(None, ge=1), limit: int=Query(24, ge=1, le=50), user=Depends(get_current_user), db=Depends(store)):
    return present_list(db.bookmarks.listing(user['id'], before, limit), request)


@router.get('/posts/{post_id}/bookmark')
def state(post_id: int, user=Depends(get_current_user), db=Depends(store)):
    return db.bookmarks.state(user['id'], post_id)


@router.put('/posts/{post_id}/bookmark')
def add(post_id: int, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:bookmark:{user["id"]}', 120)], 600)
    return db.bookmarks.set(user['id'], post_id, True)


@router.delete('/posts/{post_id}/bookmark')
def remove(post_id: int, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:bookmark:{user["id"]}', 120)], 600)
    return db.bookmarks.set(user['id'], post_id, False)
