from fastapi import Depends, HTTPException, Query, Request
from app.api.errors import ApiRouter
from app.api.dependencies import get_current_user, get_rate_limiter
from app.services.rate_limits import enforce_limit
from app.api.v1.community.dependencies import store, present, present_list, public_user, present_pet, image_response
from app.api.schemas.community import CreatePet, EditPet

router = ApiRouter()

@router.get('/me/pets')
def my_pets(user=Depends(get_current_user), db=Depends(store)):
    return {'items': [present_pet(pet) for pet in db.pets(user['id'])]}

@router.post('/me/pets', status_code=201)
def create_pet(body: CreatePet, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:pets:{user['id']}', 30)], 600)
    return present_pet(db.write_pet(user['id'], body.model_dump(mode='json', exclude={'request_key'}), request_key=str(body.request_key)))

@router.put('/me/pets/{pet_id}')
def edit_pet(pet_id: int, body: EditPet, user=Depends(get_current_user), db=Depends(store), limiter=Depends(get_rate_limiter)):
    enforce_limit(limiter, [(f'community:pets:{user['id']}', 30)], 600)
    return present_pet(db.write_pet(user['id'], body.model_dump(mode='json', exclude={'version'}), pet_id=pet_id, version=body.version))

@router.delete('/me/pets/{pet_id}')
def delete_pet(pet_id: int, version: int=Query(..., ge=1), user=Depends(get_current_user), db=Depends(store)):
    db.delete_pet(pet_id, user['id'], version)
    return {'success': True}

@router.get('/pets/{pet_id}')
def pet_profile(pet_id: int, request: Request, db=Depends(store)):
    pet = db.pet(pet_id)
    public_user(pet['user_id'], request)
    return {**present_pet(pet), 'owner': present({'user_id': pet['user_id']}, request)['author'], 'post_count': db.listing(pet_id=pet_id, limit=1)['total']}

@router.get('/pets/{pet_id}/posts')
def pet_posts(pet_id: int, request: Request, before: int | None=Query(None, ge=1), limit: int=Query(24, ge=1, le=50), db=Depends(store)):
    public_user(db.pet(pet_id)['user_id'], request)
    return present_list(db.listing(pet_id=pet_id, before=before, limit=limit), request)

@router.get('/pets/{pet_id}/photo/{media_id}')
def pet_photo(pet_id: int, media_id: str, request: Request, db=Depends(store)):
    pet = db.pet(pet_id)
    public_user(pet['user_id'], request)
    if not pet['photo_id'] or pet['photo_id'] != media_id:
        raise HTTPException(404, '宠物照片不可用')
    return image_response(request, media_id, True)
