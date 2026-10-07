from fastapi import Depends, Query, Request
from app.api.errors import ApiRouter
from typing import Literal
from app.api.dependencies import get_current_user, get_rate_limiter
from app.services.rate_limits import enforce_limit
from app.api.v1.community.dependencies import store, present_list, public_user
from app.api.schemas.community import Category

router = ApiRouter()

@router.get('/users/{user_id}/social')
def social_counts(user_id: int, request: Request, db=Depends(store)):
    public_user(user_id, request)
    return db.follow_counts(user_id)

@router.get('/users/{user_id}/follow')
def follow_state(user_id: int, request: Request, user=Depends(get_current_user), db=Depends(store)):
    public_user(user_id, request)
    return db.follow_state(user['id'], user_id)

@router.put('/users/{user_id}/follow')
def follow_user(user_id: int, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:follow:{user['id']}', 120)], 600)
    return db.set_follow(user['id'], user_id, True)

@router.delete('/users/{user_id}/follow')
def unfollow_user(user_id: int, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:follow:{user['id']}', 120)], 600)
    return db.set_follow(user['id'], user_id, False)

@router.get('/me/connections')
def my_connections(kind: Literal['following', 'followers']='following', before: int | None=Query(None, ge=1), limit: int=Query(24, ge=1, le=50), user=Depends(get_current_user), db=Depends(store)):
    return db.connections(user['id'], kind, before, limit)

@router.get('/me/following/posts')
def following_posts(request: Request, before: int | None=Query(None, ge=1), limit: int=Query(24, ge=1, le=50), category: Category | None=None, user=Depends(get_current_user), db=Depends(store)):
    return present_list(db.listing(following=user['id'], before=before, limit=limit, category=category), request)
