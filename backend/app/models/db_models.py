import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    histories: Mapped[list["ChatHistory"]] = relationship("ChatHistory", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    original_name: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing | indexed | error
    uploaded_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    markdown_path: Mapped[str | None] = mapped_column(String, nullable=True)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str] = mapped_column(Text, default="[]")  # JSON 문자열
    provider: Mapped[str] = mapped_column(String(20), default="gemini")
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    from_3gpp: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="histories")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    history_id: Mapped[str] = mapped_column(String, ForeignKey("chat_history.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 (좋아요) or -1 (싫어요)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    """앱 설정 키-값 저장소 (예: Gemini API 키 등)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ParsedChunkDB(Base):
    __tablename__ = "parsed_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # chunk-xxxx
    doc_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # text | table | image
    content: Mapped[str] = mapped_column(Text, default="")
    processed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[int] = mapped_column(Integer, default=1)
    section: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)  # 문서 내 순서 (0-based)
    is_heading: Mapped[bool] = mapped_column(Boolean, default=False)
    heading_level: Mapped[int] = mapped_column(Integer, default=0)
    image_b64: Mapped[str | None] = mapped_column(Text, nullable=True)   # data URI (이미지, VLM 전)
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)  # VLM save 후 경로
    bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)   # {"x0","y0","x1","y1","pw","ph"}
    status: Mapped[str] = mapped_column(String(20), default="pending")   # pending | confirmed | discarded
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
