"""
섹션 단위 청킹 모듈.
- 섹션 경계(heading) 보존
- 슬라이딩 윈도우 (max_tokens, overlap)
- 표·이미지는 독립 청크로 분할 금지
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.modules.pdf_parser import ChunkType, ParsedChunk


@dataclass
class IndexChunk:
    """벡터 DB 인덱싱용 최종 청크."""
    id: str
    content: str           # 임베딩할 텍스트
    doc_id: str
    page: int
    section: str
    chunk_type: str        # "text" | "table" | "image"
    image_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _approx_tokens(text: str) -> int:
    """간이 토큰 추정: 한글은 1자=2토큰, 영어는 4자=1토큰."""
    korean = sum(1 for c in text if "\uAC00" <= c <= "\uD7A3")
    other = len(text) - korean
    return korean * 2 + other // 4


def _split_text(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    """긴 텍스트를 슬라이딩 윈도우로 분할."""
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start
        token_count = 0
        while end < len(words):
            token_count += _approx_tokens(words[end]) + 1
            if token_count > max_tokens:
                break
            end += 1
        chunk_text = " ".join(words[start:end])
        if chunk_text.strip():
            chunks.append(chunk_text)
        if end >= len(words):
            break
        # overlap: 뒤로 돌아가기
        overlap_count = 0
        back = end
        while back > start and overlap_count < overlap_tokens:
            back -= 1
            overlap_count += _approx_tokens(words[back]) + 1
        start = max(back, start + 1)

    return chunks


def build_index_chunks(parsed_chunks: list[ParsedChunk], doc_id: str) -> list[IndexChunk]:
    """
    ParsedChunk 리스트 → IndexChunk 리스트.
    - 텍스트: max_tokens 초과 시 슬라이딩 윈도우 분할
    - 표·이미지: 항상 독립 청크 (분할 금지)
    """
    max_tokens = settings.chunk_max_tokens
    overlap = settings.chunk_overlap_tokens
    index_chunks: list[IndexChunk] = []
    idx = 0

    for chunk in parsed_chunks:
        if chunk.type == ChunkType.TEXT:
            if _approx_tokens(chunk.content) <= max_tokens:
                index_chunks.append(IndexChunk(
                    id=f"{doc_id}-{idx}",
                    content=chunk.content,
                    doc_id=doc_id,
                    page=chunk.page,
                    section=chunk.section,
                    chunk_type="text",
                    metadata=chunk.metadata,
                ))
                idx += 1
            else:
                for sub in _split_text(chunk.content, max_tokens, overlap):
                    index_chunks.append(IndexChunk(
                        id=f"{doc_id}-{idx}",
                        content=sub,
                        doc_id=doc_id,
                        page=chunk.page,
                        section=chunk.section,
                        chunk_type="text",
                        metadata=chunk.metadata,
                    ))
                    idx += 1

        elif chunk.type == ChunkType.TABLE:
            # 표는 분할 금지 — 그대로 하나의 청크
            index_chunks.append(IndexChunk(
                id=f"{doc_id}-{idx}",
                content=f"[표] 섹션: {chunk.section}\n{chunk.content}",
                doc_id=doc_id,
                page=chunk.page,
                section=chunk.section,
                chunk_type="table",
            ))
            idx += 1

        elif chunk.type == ChunkType.IMAGE:
            # 이미지는 VLM이 생성한 description이 content에 채워진 후 인덱싱
            if chunk.content:
                index_chunks.append(IndexChunk(
                    id=f"{doc_id}-{idx}",
                    content=f"[이미지 설명] 섹션: {chunk.section}\n{chunk.content}",
                    doc_id=doc_id,
                    page=chunk.page,
                    section=chunk.section,
                    chunk_type="image",
                    image_path=chunk.metadata.get("image_path"),
                ))
                idx += 1

    return index_chunks
