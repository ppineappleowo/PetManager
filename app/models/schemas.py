from typing import Optional, List

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    image_url: Optional[str] = None
    thread_id: str


class RAGAddRequest(BaseModel):
    documents: List[str]
