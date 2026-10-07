from datetime import datetime, timedelta, timezone
import jwt
from app.core.errors import BusinessError

def login(users, settings, identifier, password):
    user = users.authenticate(identifier, password)
    if user is None:
        raise BusinessError(401, '用户名或密码错误')
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {'sub': str(user['id']), 'username': user['username'], 'exp': expire, 'ver': user['token_version']}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {'access_token': token, 'username': user['username']}

def authenticate_token(users, settings, token):
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], options={'require': ['sub', 'exp']})
        user_id = int(payload.get('sub'))
    except jwt.ExpiredSignatureError:
        raise BusinessError(401, '认证令牌已过期，请重新登录') from None
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise BusinessError(401, '无效的认证令牌') from None
    user = users.get_by_id(user_id)
    if user is None:
        raise BusinessError(401, '用户不存在')
    if payload.get('ver', 0) != user['token_version']:
        raise BusinessError(401, '密码已修改，请重新登录')
    if user.get('disabled'):
        raise BusinessError(401, '账号已被禁用，请联系管理员')
    return user
