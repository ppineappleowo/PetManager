import re
from typing import Optional, List

from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    message: str
    image_url: Optional[str] = None
    thread_id: str


class RAGAddRequest(BaseModel):
    documents: List[str]


# ==================== 认证 Schema ====================

class UserRegister(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 32:
            raise ValueError("用户名长度需在 2-32 个字符之间")
        if not re.match(r'^[a-zA-Z0-9_一-鿿]+$', v):
            raise ValueError("用户名只能包含字母、数字、下划线或中文")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6 or len(v) > 64:
            raise ValueError("密码长度需在 6-64 个字符之间")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserInfo(BaseModel):
    id: int
    username: str
    created_at: Optional[str] = None
