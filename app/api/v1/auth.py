"""用户认证路由 —— 注册、登录、获取当前用户信息。"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings
from app.core.dependencies import get_settings, get_user_manager, get_current_user
from app.common.user_manager import UserManager
from app.models.schemas import UserRegister, UserLogin, TokenResponse, UserInfo

router = APIRouter()


# ==================== 注册 ====================

@router.post("/auth/register", response_model=UserInfo, status_code=201)
def register(
    request: UserRegister,
    user_manager: UserManager = Depends(get_user_manager),
):
    """注册新用户。用户名全局唯一，密码至少 6 位。"""
    user = user_manager.create_user(request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已被注册",
        )
    return UserInfo(
        id=user["id"],
        username=user["username"],
        created_at=user.get("created_at"),
    )


# ==================== 登录 ====================

@router.post("/auth/login", response_model=TokenResponse)
def login(
    request: UserLogin,
    user_manager: UserManager = Depends(get_user_manager),
    settings: Settings = Depends(get_settings),
):
    """用户名 + 密码登录，返回 JWT access token。"""
    user = user_manager.authenticate(request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return TokenResponse(
        access_token=token,
        username=user["username"],
    )


# ==================== 当前用户 ====================

@router.get("/auth/me", response_model=UserInfo)
def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户的个人信息（需 Bearer Token）。"""
    return UserInfo(
        id=current_user["id"],
        username=current_user["username"],
        created_at=current_user.get("created_at"),
    )
