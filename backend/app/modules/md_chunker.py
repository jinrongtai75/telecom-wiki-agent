"""
MD 파일 기반 섹션 청킹 모듈.

MD 파일(진실의 원본)을 파싱하여 섹션 단위 IndexChunk 목록을 반환.
- 각 청크에 헤딩 컨텍스트 + 요약 prefix 포함 → 임베딩 품질 향상
- 표·이미지는 섹션 컨텍스트와 함께 독립 청크
- 긴 섹션은 슬라이딩 윈도우 분할 (heading prefix 반복)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.modules.chunker import IndexChunk, _approx_tokens, _split_text

# <!-- obj:ID type:TYPE page:N --> 패턴
_OBJ_RE = re.compile(
    r"<!--\s*obj:(\S+)\s+type:(\S+)\s+page:(\d+)(?:\s+\S+)?\s*-->"
)
# <!-- doc:ID source:NAME ... --> 패턴
_DOC_RE = re.compile(r"<!--\s*doc:\S+\s+source:\S+")
# 헤딩 패턴
_HEADING_RE = re.compile(r"^(#+)\s+(.+)$")
# summary 블록 prefix 제거
_SUMMARY_RE = re.compile(r"^>\s*\*\*요약\*\*:\s*")


@dataclass
class _Block:
    """MD 파일에서 파싱된 단일 obj 블록."""
    obj_id: str
    type: str        # text | summary | table | image
    page: int
    content: str
    is_heading: bool = False
    heading_level: int = 0
    heading_text: str = ""


@dataclass
class _Section:
    """헤딩 기준으로 묶인 섹션."""
    heading: str
    heading_level: int
    summary: str
    body_blocks: list[_Block] = field(default_factory=list)
    page: int = 1


class MDChunker:
    """MD 파일 → 섹션 기반 IndexChunk 리스트."""

    def chunk_from_file(self, md_path: str, doc_id: str) -> list[IndexChunk]:
        """파일 경로로부터 청킹."""
        content = Path(md_path).read_text(encoding="utf-8")
        return self.chunk_from_text(content, doc_id)

    def chunk_from_text(self, content: str, doc_id: str) -> list[IndexChunk]:
        """MD 텍스트로부터 청킹."""
        blocks = self._parse_blocks(content)
        sections = self._group_into_sections(blocks)
        return self._build_index_chunks(sections, doc_id)

    # ── 파싱 ──────────────────────────────────────────────────────────────────

    def _parse_blocks(self, content: str) -> list[_Block]:
        """<!-- obj: --> 주석 기준으로 블록 파싱."""
        blocks: list[_Block] = []
        lines = content.splitlines()
        current_meta: dict | None = None
        current_lines: list[str] = []

        def _flush() -> None:
            if current_meta is None:
                return
            raw = "\n".join(current_lines).strip()
            block = _Block(
                obj_id=current_meta["id"],
                type=current_meta["type"],
                page=current_meta["page"],
                content=raw,
            )
            # heading 탐지 (type=text이고 첫 줄이 '#'으로 시작)
            if block.type == "text" and raw:
                m = _HEADING_RE.match(raw.split("\n")[0])
                if m:
                    block.is_heading = True
                    block.heading_level = len(m.group(1))
                    block.heading_text = m.group(2).strip()
            # summary: "> **요약**: " prefix 제거
            if block.type == "summary":
                lines_s = raw.splitlines()
                if lines_s:
                    lines_s[0] = _SUMMARY_RE.sub("", lines_s[0])
                block.content = "\n".join(lines_s).strip()
            blocks.append(block)

        for line in lines:
            stripped = line.strip()
            m = _OBJ_RE.match(stripped)
            if m:
                _flush()
                current_meta = {
                    "id": m.group(1),
                    "type": m.group(2),
                    "page": int(m.group(3)),
                }
                current_lines = []
            elif _DOC_RE.match(stripped):
                # doc 헤더 라인 무시
                continue
            elif current_meta is not None:
                current_lines.append(line)

        _flush()
        return blocks

    # ── 섹션 그룹화 ───────────────────────────────────────────────────────────

    def _group_into_sections(self, blocks: list[_Block]) -> list[_Section]:
        """heading 블록 기준으로 섹션 그룹화."""
        sections: list[_Section] = []
        current: _Section | None = None

        for block in blocks:
            if block.is_heading:
                current = _Section(
                    heading=block.heading_text,
                    heading_level=block.heading_level,
                    summary="",
                    page=block.page,
                )
                sections.append(current)
            elif block.type == "summary":
                if current is not None:
                    current.summary = block.content
                # heading 없는 summary는 무시
            else:
                if current is None:
                    # 헤딩 이전 서두 블록 → 빈 헤딩 섹션으로 수용
                    current = _Section(heading="", heading_level=0, summary="", page=block.page)
                    sections.append(current)
                current.body_blocks.append(block)

        return sections

    # ── IndexChunk 생성 ───────────────────────────────────────────────────────

    def _build_index_chunks(self, sections: list[_Section], doc_id: str) -> list[IndexChunk]:
        max_tokens = settings.chunk_max_tokens
        overlap = settings.chunk_overlap_tokens
        index_chunks: list[IndexChunk] = []
        idx = 0

        for section in sections:
            heading = section.heading
            summary = section.summary
            page = section.page

            # 섹션 prefix: "[섹션: {heading}]\n요약: {summary}"
            prefix_parts: list[str] = []
            if heading:
                prefix_parts.append(f"[섹션: {heading}]")
            if summary:
                prefix_parts.append(f"요약: {summary}")
            prefix = "\n".join(prefix_parts)

            # body 분류
            text_parts: list[str] = []
            special_blocks: list[_Block] = []

            for block in section.body_blocks:
                if block.type in ("table", "image"):
                    special_blocks.append(block)
                elif block.content:
                    text_parts.append(block.content)

            # 텍스트 청크
            body_text = "\n\n".join(text_parts)
            full_text = f"{prefix}\n\n{body_text}".strip() if prefix else body_text.strip()

            if full_text:
                prefix_tokens = _approx_tokens(prefix) + 2 if prefix else 0
                if _approx_tokens(full_text) <= max_tokens:
                    index_chunks.append(IndexChunk(
                        id=f"{doc_id}-md-{idx}",
                        content=full_text,
                        doc_id=doc_id,
                        page=page,
                        section=heading,
                        chunk_type="text",
                    ))
                    idx += 1
                else:
                    # body만 분할, 각 sub-chunk에 prefix 반복
                    body_max = max(64, max_tokens - prefix_tokens)
                    for sub in _split_text(body_text, body_max, overlap):
                        sub_text = f"{prefix}\n\n{sub}".strip() if prefix else sub
                        index_chunks.append(IndexChunk(
                            id=f"{doc_id}-md-{idx}",
                            content=sub_text,
                            doc_id=doc_id,
                            page=page,
                            section=heading,
                            chunk_type="text",
                        ))
                        idx += 1
            elif prefix:
                # body 없이 heading만 있는 경우
                index_chunks.append(IndexChunk(
                    id=f"{doc_id}-md-{idx}",
                    content=prefix,
                    doc_id=doc_id,
                    page=page,
                    section=heading,
                    chunk_type="text",
                ))
                idx += 1

            # 표·이미지 청크
            for block in special_blocks:
                if block.type == "table" and block.content:
                    ctx = f"[표] 섹션: {heading}\n{block.content}" if heading else f"[표]\n{block.content}"
                    index_chunks.append(IndexChunk(
                        id=f"{doc_id}-md-{idx}",
                        content=ctx,
                        doc_id=doc_id,
                        page=block.page,
                        section=heading,
                        chunk_type="table",
                    ))
                    idx += 1
                elif block.type == "image" and block.content:
                    # image_path 추출
                    img_m = re.search(r"!\[.*?\]\((.+?)\)", block.content)
                    image_path = img_m.group(1) if img_m else None
                    # 마크다운 이미지 문법 제거 후 description만 추출
                    desc = re.sub(r"!\[.*?\]\(.*?\)\n?", "", block.content).strip()
                    ctx = f"[이미지 설명] 섹션: {heading}\n{desc}" if heading else f"[이미지 설명]\n{desc}"
                    if ctx.strip():
                        index_chunks.append(IndexChunk(
                            id=f"{doc_id}-md-{idx}",
                            content=ctx,
                            doc_id=doc_id,
                            page=block.page,
                            section=heading,
                            chunk_type="image",
                            image_path=image_path,
                        ))
                        idx += 1

        return index_chunks


md_chunker = MDChunker()
