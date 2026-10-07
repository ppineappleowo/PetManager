from fastapi import Depends, Query, Request
from typing import Literal
from app.api.errors import ApiRouter
from app.api.dependencies import get_current_user, get_rate_limiter
from app.services.rate_limits import enforce_limit
from app.api.v1.community.dependencies import store, present, present_list, CATEGORIES
from app.api.schemas.community import Category, CreatePost, EditPost

router = ApiRouter()

@router.get('/categories')
def categories():
    return CATEGORIES

@router.get('/posts')
def feed(request: Request, category: Category | None=None, before: int | None=Query(None, ge=1), limit: int=Query(24, ge=1, le=50), q: str=Query('', max_length=100), tag: str=Query('', max_length=12), sort: Literal['latest','oldest']='latest', db=Depends(store)):
    return present_list(db.discover(category=category, before=before, limit=limit, q=q, tag=tag, sort=sort), request)

@router.get('/topics')
def topics(category: Category | None=None, q: str=Query('', max_length=12), limit: int=Query(20, ge=1, le=50), db=Depends(store)):
    return db.topics(category, q, limit)

@router.get('/mine')
def mine(request: Request, before: int | None=Query(None, ge=1), limit: int=Query(24, ge=1, le=50), user=Depends(get_current_user), db=Depends(store)):
    return present_list(db.listing(owner=user['id'], before=before, limit=limit), request)

@router.get('/mine/{post_id}')
def own_post(post_id: int, request: Request, user=Depends(get_current_user), db=Depends(store)):
    return present(db.get(post_id, owner=user['id']), request)

@router.post('/posts', status_code=201)
def create(body: CreatePost, request: Request, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:publish:{user['id']}', 10)], 600)
    return present(db.write(user['id'], body.model_dump(exclude={'request_key'}), request_key=str(body.request_key)), request)

@router.get('/posts/{post_id}')
def detail(post_id: int, request: Request, db=Depends(store)):
    return present(db.get(post_id), request)

@router.put('/posts/{post_id}')
def edit(post_id: int, body: EditPost, request: Request, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:edit:{user['id']}', 30)], 600)
    return present(db.write(user['id'], body.model_dump(exclude={'version'}), post_id=post_id, version=body.version), request)

@router.delete('/posts/{post_id}')
def delete(post_id: int, user=Depends(get_current_user), db=Depends(store)):
    db.delete(post_id, user['id'])
    return {'success': True}
