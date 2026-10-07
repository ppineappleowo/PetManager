from fastapi import Depends, Query, Request
from app.api.errors import ApiRouter
from app.api.dependencies import get_current_user, get_rate_limiter
from app.services.rate_limits import enforce_limit
from app.api.v1.community.dependencies import store, present_comment
from app.api.schemas.community import CommentInput, ReportInput

router = ApiRouter()

@router.get('/posts/{post_id}/comments')
def comments(post_id: int, request: Request, after: int=Query(0, ge=0), limit: int=Query(20, ge=1, le=50), db=Depends(store)):
    data = db.comments(post_id, after, limit)
    data['items'] = [present_comment(row, request, db) for row in data['items']]
    return data

@router.post('/posts/{post_id}/comments', status_code=201)
def add_comment(post_id: int, body: CommentInput, request: Request, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:comment:{user['id']}', 30)], 600)
    return present_comment(db.add_comment(post_id, user['id'], body.body, body.reply_to, str(body.request_key)), request, db)

@router.delete('/comments/{comment_id}')
def delete_comment(comment_id: int, user=Depends(get_current_user), db=Depends(store)):
    db.delete_comment(comment_id, user['id'])
    return {'success': True}

@router.get('/posts/{post_id}/interaction')
def interaction(post_id: int, user=Depends(get_current_user), db=Depends(store)):
    db.get(post_id)
    return db.interaction_counts(post_id, user['id'])

@router.put('/posts/{post_id}/like')
def like(post_id: int, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:like:{user['id']}', 120)], 600)
    return db.like(post_id, user['id'], True)

@router.delete('/posts/{post_id}/like')
def unlike(post_id: int, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:like:{user['id']}', 120)], 600)
    return db.like(post_id, user['id'], False)

@router.post('/reports', status_code=201)
def report(body: ReportInput, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:report:{user['id']}', 10)], 600)
    return db.report(user['id'], body.target_type, body.target_id, body.reason)
