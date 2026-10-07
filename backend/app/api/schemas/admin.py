from typing import Literal
from pydantic import BaseModel, Field

class UserUpdate(BaseModel):
    role: Literal['admin', 'user'] | None = None
    disabled: bool | None = None
    revoke: bool = False

class KnowledgeInput(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
