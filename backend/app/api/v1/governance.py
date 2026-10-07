from typing import Literal
from fastapi import Depends, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from app.api.errors import ApiRouter
from app.api.dependencies import get_admin_user,get_current_user,get_user_manager,get_avatar_media
from app.api.v1.community.dependencies import store,image_response
from app.services.community.metrics import community_metrics

router = ApiRouter()


class GovernanceInput(BaseModel):
    field: Literal['profile','avatar'] = 'profile'
    hidden: bool
    reason: str = Field(min_length=1,max_length=300)
    version: int = Field(ge=1)

    @field_validator('reason')
    @classmethod
    def reason_required(cls, value):
        if not value.strip():
            raise ValueError('请填写处理原因')
        return value.strip()


@router.patch('/admin/users/{user_id}/moderation')
def moderate_user(user_id: int, body: GovernanceInput, actor=Depends(get_admin_user), users=Depends(get_user_manager)):
    users.moderate(user_id,actor['id'],body.field,body.hidden,body.reason,body.version)
    return {'success':True}


@router.get('/admin/users/{user_id}/avatar',dependencies=[Depends(get_admin_user)])
def admin_avatar(user_id: int, users=Depends(get_user_manager), media=Depends(get_avatar_media)):
    from fastapi import HTTPException
    user = users.get_by_id(user_id)
    if not user or not user['avatar_id']:
        raise HTTPException(404,'头像不可用')
    return Response(media.get(user['avatar_id'],True),media_type='image/webp',headers={'Cache-Control':'no-store'})


@router.get('/admin/pets',dependencies=[Depends(get_admin_user)])
def admin_pets(before: int | None=Query(None,ge=1),limit: int=Query(20,ge=1,le=50),db=Depends(store)):
    return db.admin_pets(before,limit)


@router.get('/admin/pets/{pet_id}/photo',dependencies=[Depends(get_admin_user)])
def admin_pet_photo(pet_id: int,request: Request,db=Depends(store)):
    from fastapi import HTTPException
    row = db.admin_pet(pet_id)
    if not row['photo_id']:
        raise HTTPException(404,'照片不可用')
    return image_response(request,row['photo_id'],False)


@router.patch('/admin/pets/{pet_id}/moderation')
def moderate_pet(pet_id: int,body: GovernanceInput,actor=Depends(get_admin_user),db=Depends(store)):
    db.moderate_pet(pet_id,actor['id'],body.hidden,body.reason,body.version)
    return {'success':True}


@router.get('/admin/governance',dependencies=[Depends(get_admin_user)])
def audit(response: Response,kind: Literal['users','community']='community',before: int | None=Query(None,ge=1),limit: int=Query(20,ge=1,le=50),users=Depends(get_user_manager),db=Depends(store)):
    response.headers['Cache-Control']='no-store'
    return (users if kind=='users' else db).audit(before=before,limit=limit)


@router.get('/community/me/moderation')
def my_moderation(response: Response,kind: Literal['users','community']='community',before: int | None=Query(None,ge=1),limit: int=Query(20,ge=1,le=50),user=Depends(get_current_user),users=Depends(get_user_manager),db=Depends(store)):
    response.headers['Cache-Control']='no-store'
    return (users if kind=='users' else db).audit(owner=user['id'],before=before,limit=limit)


@router.get('/admin/community-metrics',dependencies=[Depends(get_admin_user)])
def metrics(db=Depends(store)):
    return community_metrics(db)
