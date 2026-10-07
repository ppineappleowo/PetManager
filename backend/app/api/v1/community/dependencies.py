from fastapi import Request, Response
from app.services.community.presentation import CommunityPresenter
CATEGORIES = dict(cat='猫咪', dog='狗狗', bird='鸟类', fish='鱼类', small='小宠', reptile='爬宠', other='其他', general='多宠 / 综合')

def store(request: Request):
    return request.app.state.community_store

def presenter(request):
    return CommunityPresenter(request.app.state.user_manager, store(request))

def present(post, request):
    return presenter(request).present(post)

def present_list(data, request):
    return presenter(request).present_list(data)

def public_user(user_id, request):
    return presenter(request).public_user(user_id)

def present_pet(pet):
    return CommunityPresenter(None, None).present_pet(pet)

def present_comment(row, request, db):
    return presenter(request).present_comment(row)

def image_response(request, media_id, thumbnail):
    data = request.app.state.community_media.get(media_id, thumbnail)
    return Response(data, media_type='image/webp', headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
