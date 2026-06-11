from pydantic import BaseModel


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


class AskRequest(BaseModel):
    question: str


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


class IndexResponse(BaseModel):
    changed_sources: list[str]
    skipped_sources: list[str]
    removed_sources: list[str]
    written_points: int
    collection_name: str
    storage_path: str
    logs: list[str]
