import re
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID


class ChatRequest(BaseModel):
    pet_id: int | None = Field(default=None, ge=1)
    message: str = Field(max_length=20000)
    image_url: Optional[str] = Field(default=None, max_length=4096)
    thread_id: str = Field(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9_-]+$')
    request_id: UUID

    @model_validator(mode="after")
    def require_content(self):
        if not self.message.strip() and not self.image_url:
            raise ValueError("请输入消息或选择图片")
        return self


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
        if not v.strip():
            raise ValueError("密码不能全部为空格")
        return v


class UserLogin(UserRegister):
    pass


class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=64)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value):
        return UserRegister.validate_password(value)

    @model_validator(mode="after")
    def different_password(self):
        if self.old_password == self.new_password:
            raise ValueError("新密码不能与原密码相同")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserInfo(BaseModel):
    profile_hidden: int = 0
    avatar_hidden: int = 0
    profile_version: int = 1
    avatar_id: str = ''
    id: int
    username: str
    created_at: Optional[str] = None
    role: str = "user"
    phone: Optional[str] = None
    nickname: str = ''
    bio: str = ''


class PhoneRegister(BaseModel):
    phone: str = Field(pattern=r'^1[3-9][0-9]{9}$')
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, value):
        return UserRegister.validate_password(value)


class ProfileUpdate(BaseModel):
    username: str
    nickname: str = Field(default='', max_length=32)
    bio: str = Field(default='', max_length=300)

    @field_validator('username')
    @classmethod
    def validate_username(cls, value):
        return UserRegister.validate_username(value)
