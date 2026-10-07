from app.services.rate_limits import consume, enforce_limit
from app.services import authentication
from app.api.errors import ApiRouter
"""用户认证路由 —— 注册、登录、获取当前用户信息。"""
from fastapi import Depends, HTTPException, Request
from app.core.config import Settings
from app.api.dependencies import get_settings, get_user_manager, get_current_user, get_rate_limiter
from app.services.users import UserService
from app.api.schemas.auth_chat import UserLogin, TokenResponse, UserInfo, PasswordChange, ProfileUpdate, PhoneRegister
router = ApiRouter()

@router.post('/auth/register', response_model=UserInfo, status_code=201)
def register(body: PhoneRegister, request: Request, manager=Depends(get_user_manager), limiter=Depends(get_rate_limiter)):
    ip = request.client.host if request.client else 'unknown'
    enforce_limit(limiter, [('register:phone:' + body.phone, 10), ('register:ip:' + ip, 30)], 300)
    return UserInfo(**manager.register_phone(body.phone, body.password))

@router.post('/auth/login', response_model=TokenResponse)
def login(request: UserLogin, user_manager: UserService=Depends(get_user_manager), settings: Settings=Depends(get_settings)):
    """用户名 + 密码登录，返回 JWT access token。"""
    return TokenResponse(**authentication.login(user_manager, settings, request.username, request.password))

@router.get('/auth/me', response_model=UserInfo)
def get_me(current_user: dict=Depends(get_current_user)):
    """获取当前登录用户的个人信息（需 Bearer Token）。"""
    return UserInfo(**current_user)

@router.patch('/auth/me', response_model=UserInfo)
def update_profile(request: ProfileUpdate, current_user=Depends(get_current_user), user_manager=Depends(get_user_manager)):
    return UserInfo(**user_manager.update_profile(current_user['id'], **request.model_dump()))

@router.post('/auth/password')
def change_password(request: PasswordChange, current_user=Depends(get_current_user), user_manager=Depends(get_user_manager), settings=Depends(get_settings), limiter=Depends(get_rate_limiter)):
    retry = consume(limiter, [('password:' + str(current_user['id']), settings.login_max_attempts)], settings.login_window_seconds)
    if retry:
        raise HTTPException(429, f'尝试过于频繁，请在 {retry} 秒后重试', headers={'Retry-After': str(retry)})
    if not user_manager.change_password(current_user['id'], request.old_password, request.new_password, current_user['token_version']):
        raise HTTPException(400, '原密码错误或登录状态已变化')
    return {'success': True, 'message': '密码已修改，请重新登录'}
