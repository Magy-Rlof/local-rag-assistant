from pydantic import BaseModel, Field
from typing import Literal


class DocumentInfo(BaseModel):
    name: str
    category: str
    source: str
    size_bytes: int
    modified_at: str
    editable: bool
    deletable: bool


class DocumentContent(BaseModel):
    name: str
    category: str
    source: str
    content: str


class UpdateDocumentRequest(BaseModel):
    content: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question: str
    history: list[ChatMessage] = Field(default_factory=list)


class SourceInfo(BaseModel):
    source_file: str
    title: str
    score: float | None = None


class AskResponse(BaseModel):
    answer: str
    truncated: bool
    sources: list[SourceInfo]
    retrieval_seconds: float
    generation_seconds: float
    mode: str


class IndexResponse(BaseModel):
    changed_sources: list[str]
    skipped_sources: list[str]
    removed_sources: list[str]
    written_points: int
    collection_name: str
    storage_path: str
    logs: list[str]
