from datetime import datetime

from pydantic import BaseModel, field_validator


# Auth
class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not v or len(v) < 3 or len(v) > 50:
            raise ValueError("username must be 3-50 chars")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("password must be at least 6 chars")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class InitAdminRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not v or len(v) < 3 or len(v) > 50:
            raise ValueError("username must be 3-50 chars")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("password must be at least 6 chars")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False


# Search
class SearchRequest(BaseModel):
    question: str
    provider: str = "gemini"
    api_token: str = ""  # Gemini API 키 (없으면 DB 저장 키 사용)

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        if len(v) > 2000:
            raise ValueError("question too long (max 2000 chars)")
        return v

    @field_validator("provider")
    @classmethod
    def provider_valid(cls, v: str) -> str:
        if v not in ("gemini",):
            return "gemini"
        return v


class SourceInfo(BaseModel):
    doc_id: str
    filename: str
    page: int
    section: str
    score: float
    image_path: str | None = None
    from_3gpp: bool = False
    has_pdf: bool = False


class SearchResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]
    provider: str
    history_id: str


# Documents
class DocumentMeta(BaseModel):
    id: str
    original_name: str
    file_size: int
    chunk_count: int
    status: str
    uploaded_at: datetime
    indexed_at: datetime | None = None
    markdown_path: str | None = None


class NoiseCandidateItem(BaseModel):
    text: str
    count: int
    chunk_ids: list[str]


class NoiseCandidatesResponse(BaseModel):
    candidates: list[NoiseCandidateItem]


class SummarizeResponse(BaseModel):
    inserted: int


# Chunks
class ChunkInfo(BaseModel):
    id: str
    doc_id: str
    type: str
    content: str
    processed_content: str | None = None
    page: int
    section: str
    order: int
    is_heading: bool
    heading_level: int
    image_b64: str | None = None
    image_path: str | None = None
    bbox_json: str | None = None
    status: str


class ChunkUpdateRequest(BaseModel):
    content: str | None = None
    processed_content: str | None = None
    is_heading: bool | None = None


class ReorderRequest(BaseModel):
    ordered_ids: list[str]


class VlmRequest(BaseModel):
    api_token: str = ""  # Gemini API 키 (없으면 DB 저장 키 사용)


class ChatEditRequest(BaseModel):
    message: str
    api_token: str = ""  # Gemini API 키 (없으면 DB 저장 키 사용)


# History
class HistoryItem(BaseModel):
    id: str
    question: str
    answer: str
    sources: list[SourceInfo]
    provider: str
    created_at: datetime


# Feedback
class FeedbackRequest(BaseModel):
    history_id: str
    rating: int

    @field_validator("rating")
    @classmethod
    def rating_valid(cls, v: int) -> int:
        if v not in (1, -1):
            raise ValueError("rating must be 1 or -1")
        return v
