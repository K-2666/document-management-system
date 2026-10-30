from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentShareCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    permission: Literal["viewer", "editor"] = "viewer"


class DocumentShareResponse(BaseModel):
    id: int
    document_id: int
    shared_with_user_id: int
    shared_by_user_id: int
    permission: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SharedDocumentResponse(BaseModel):
    id: int
    owner_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    permission: str

    model_config = ConfigDict(from_attributes=True)


class SharedDocumentListResponse(BaseModel):
    items: list[SharedDocumentResponse]
    total: int