from fastapi import Depends, HTTPException, Query, Request
from app.api.errors import ApiRouter
from typing import Literal
from app.api.dependencies import get_admin_user
from app.api.v1.community.dependencies import store, present, present_list, image_response
from app.api.schemas.community import Moderation, ReportResolution

router = ApiRouter()

@router.get('/admin/posts', dependencies=[Depends(get_admin_user)])
def admin_posts(request: Request, offset: int=Query(0, ge=0), limit: int=Query(20, ge=1, le=100), q: str=Query('', max_length=100), db=Depends(store)):
    return present_list(db.listing(admin=True, offset=offset, limit=limit, q=q), request)

@router.get('/admin/posts/{post_id}', dependencies=[Depends(get_admin_user)])
def admin_post(post_id: int, request: Request, db=Depends(store)):
    post = present(db.get(post_id, admin=True), request)
    post['audit'] = db.moderation_history(post_id)
    return post

@router.get('/admin/posts/{post_id}/images/{media_id}', dependencies=[Depends(get_admin_user)])
def admin_image(post_id: int, media_id: str, request: Request, db=Depends(store)):
    if media_id not in db.get(post_id, admin=True)['images']:
        raise HTTPException(404, '图片不可用')
    return image_response(request, media_id, False)

@router.patch('/admin/posts/{post_id}')
def moderate(post_id: int, body: Moderation, request: Request, user=Depends(get_admin_user), db=Depends(store)):
    return present(db.moderate(post_id, user['id'], body.status, body.reason, body.version), request)

@router.get('/admin/comments', dependencies=[Depends(get_admin_user)])
def admin_comments(request: Request, post_id: int | None=Query(None, ge=1), offset: int=Query(0, ge=0), limit: int=Query(20, ge=1, le=100), db=Depends(store)):
    data = db.admin_comments(post_id, offset, limit)
    data['items'] = [present(row, request) for row in data['items']]
    return data

@router.patch('/admin/comments/{comment_id}')
def moderate_comment(comment_id: int, body: Moderation, user=Depends(get_admin_user), db=Depends(store)):
    db.moderate_comment(comment_id, user['id'], body.status, body.reason, body.version)
    return {'success': True}

@router.get('/admin/reports', dependencies=[Depends(get_admin_user)])
def admin_reports(status: Literal['open', 'resolved']='open', offset: int=Query(0, ge=0), limit: int=Query(20, ge=1, le=100), db=Depends(store)):
    return db.report_listing(status, offset, limit)

@router.patch('/admin/reports/{report_id}')
def resolve_report(report_id: int, body: ReportResolution, user=Depends(get_admin_user), db=Depends(store)):
    db.resolve_report(report_id, user['id'], body.action, body.note)
    return {'success': True}
