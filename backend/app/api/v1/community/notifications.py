from fastapi import Depends, Query, Request, Response
from app.api.schemas.community import NotificationReadThrough
from app.api.errors import ApiRouter
from app.api.dependencies import get_current_user
from app.api.v1.community.dependencies import store

router = ApiRouter()


@router.get('/me/notifications/summary')
def summary(response: Response, user=Depends(get_current_user), db=Depends(store)):
    response.headers['Cache-Control'] = 'no-store'
    return db.notifications.summary(user['id'])


@router.get('/me/notifications')
def listing(request: Request, response: Response, before: int | None=Query(None, ge=1), limit: int=Query(24, ge=1, le=50), user=Depends(get_current_user), db=Depends(store)):
    response.headers['Cache-Control'] = 'no-store'
    return db.notifications.listing(user['id'], request.app.state.user_manager, before, limit)


@router.put('/me/notifications/read-all')
def read_all(body: NotificationReadThrough, user=Depends(get_current_user), db=Depends(store)):
    db.notifications.mark_all(user['id'], body.through_id)
    return {'success': True}


@router.put('/me/notifications/{notification_id}/read')
def read(notification_id: int, user=Depends(get_current_user), db=Depends(store)):
    db.notifications.mark_read(user['id'], notification_id)
    return {'success': True}
