from typing import Literal
from uuid import UUID
from fastapi import Depends
from pydantic import BaseModel, Field
from app.api.errors import ApiRouter
from app.api.dependencies import get_chat_history,get_current_user,get_admin_user

router=ApiRouter()


class FeedbackInput(BaseModel):
    value: Literal['helpful','unhelpful','']
    note: str=Field(default='',max_length=500)


@router.put('/chat/requests/{request_id}/feedback')
def feedback(request_id: UUID,body: FeedbackInput,user=Depends(get_current_user),history=Depends(get_chat_history)):
    if hasattr(history,'initialize'):
        history.initialize()
    history.turn_store.feedback(str(user['id']),str(request_id),body.value,body.note.strip())
    return {'success':True}

@router.get('/admin/ai-metrics',dependencies=[Depends(get_admin_user)])
def ai_metrics(history=Depends(get_chat_history)):
    if hasattr(history,'initialize'):history.initialize()
    return history.turn_store.metrics()
