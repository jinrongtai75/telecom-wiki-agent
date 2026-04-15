from enum import Enum
from typing import Optional, List
from pydantic import BaseModel


class ObjectType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    SUMMARY = "summary"


class ConfirmStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    WEB = "web"


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float = 0.0
    page_height: float = 0.0


class DocumentObject(BaseModel):
    id: str
    type: ObjectType
    content: str
    order: int
    page: Optional[int] = None
    bbox: Optional[BBox] = None
    metadata: dict = {}
    is_heading: bool = False
    confirm_status: ConfirmStatus = ConfirmStatus.PENDING
    image_path: Optional[str] = None
    processed_content: Optional[str] = None


class NoisePatterns(BaseModel):
    header_patterns: List[str] = []
    footer_patterns: List[str] = []
    page_number_patterns: List[str] = []
    contains_patterns: List[str] = []


class NoiseCandidate(BaseModel):
    text: str
    count: int
    object_ids: List[str]


class ParseResult(BaseModel):
    document_id: str
    format: DocumentFormat
    objects: List[DocumentObject]
    raw_content: Optional[str] = None


class ProcessedDocument(BaseModel):
    document_id: str
    source_filename: str
    format: DocumentFormat
    objects: List[DocumentObject]
    noise_patterns_applied: Optional[NoisePatterns] = None
    created_at: str
    updated_at: str
