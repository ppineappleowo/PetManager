from typing import Literal
from fastapi import Depends, Query, Response
from app.api.errors import ApiRouter
from app.api.dependencies import get_current_user
from app.api.v1.community.dependencies import store

router = ApiRouter()


@router.get('/me/reports')
def my_reports(response: Response, status: Literal['all', 'open', 'resolved']='all',
               before: int | None=Query(None, ge=1), limit: int=Query(20, ge=1, le=50),
               user=Depends(get_current_user), db=Depends(store)):
    response.headers['Cache-Control'] = 'no-store'
    return db.report_feedback.listing(user['id'], status, before, limit)
