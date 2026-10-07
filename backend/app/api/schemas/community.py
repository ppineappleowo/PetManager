from typing import Literal
from datetime import date
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
Category = Literal['cat', 'dog', 'bird', 'fish', 'small', 'reptile', 'other', 'general']

class NotificationReadThrough(BaseModel):
    through_id: int = Field(ge=0)

class PostInput(BaseModel):
    ai_generated: bool = False
    pet_ids: list[int] = Field(default_factory=list, max_length=5)

    @field_validator('pet_ids')
    @classmethod
    def pets_valid(cls, value):
        if any((item < 1 for item in value)) or len(set(value)) != len(value):
            raise ValueError('请选择有效且不重复的宠物')
        return sorted(value)
    title: str = Field(default='', max_length=50)
    body: str = Field(min_length=1, max_length=5000)
    category: Category
    tags: list[str] = Field(default_factory=list, max_length=5)
    images: list[str] = Field(default_factory=list, max_length=9)

    @field_validator('body', 'title')
    @classmethod
    def trim(cls, value, info):
        value = value.strip()
        if info.field_name == 'body' and (not value):
            raise ValueError('正文不能为空')
        return value

    @field_validator('tags')
    @classmethod
    def tags_valid(cls, value):
        result = list(dict.fromkeys((tag.strip().lstrip('#') for tag in value if tag.strip().lstrip('#'))))
        if any((len(tag) > 12 for tag in result)):
            raise ValueError('每个标签最多 12 字')
        return result

    @field_validator('images')
    @classmethod
    def images_valid(cls, value):
        if len(set(value)) != len(value) or any((len(i) != 32 or any((c not in '0123456789abcdef' for c in i)) for i in value)):
            raise ValueError('图片标识无效或重复')
        return value

class CreatePost(PostInput):
    request_key: UUID

class EditPost(PostInput):
    version: int = Field(ge=1)

class Moderation(BaseModel):
    status: Literal['published', 'hidden']
    reason: str = Field(min_length=1, max_length=300)
    version: int = Field(ge=1)

    @field_validator('reason')
    @classmethod
    def reason_valid(cls, value):
        if not value.strip():
            raise ValueError('请填写操作原因')
        return value.strip()

class PetInput(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    species: Literal['cat', 'dog', 'bird', 'fish', 'small', 'reptile', 'other']
    breed: str = Field(default='', max_length=50)
    sex: Literal['unknown', 'male', 'female'] = 'unknown'
    birthday: date | None = None
    bio: str = Field(default='', max_length=500)
    photo_id: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')

    @field_validator('name', 'breed', 'bio')
    @classmethod
    def trim(cls, value, info):
        value = value.strip()
        if info.field_name == 'name' and (not value):
            raise ValueError('请填写宠物名字')
        return value

    @field_validator('birthday')
    @classmethod
    def birthday_valid(cls, value):
        if value and value > date.today():
            raise ValueError('生日不能晚于今天')
        return value

class CreatePet(PetInput):
    request_key: UUID

class EditPet(PetInput):
    version: int = Field(ge=1)

class CommentInput(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    reply_to: int | None = Field(default=None, ge=1)
    request_key: UUID

    @field_validator('body')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('评论不能为空')
        return value.strip()

class ReportInput(BaseModel):
    target_type: Literal['post', 'comment']
    target_id: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator('reason')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('请填写举报原因')
        return value.strip()

class ReportResolution(BaseModel):
    action: Literal['dismiss', 'hide']
    note: str = Field(min_length=1, max_length=500)

    @field_validator('note')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('请填写处理说明')
        return value.strip()
