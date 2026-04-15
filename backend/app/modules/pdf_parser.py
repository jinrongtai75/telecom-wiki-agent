"""
PDF 2-Pass 파싱 모듈.
preprocessing-master의 parser.py를 기반으로 RAG 인덱싱에 최적화.
"""
from __future__ import annotations

import base64
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import fitz  # PyMuPDF


class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"


@dataclass
class ParsedChunk:
    """PDF에서 파싱된 단일 청크. 벡터 인덱싱 전 단계."""
    id: str = field(default_factory=lambda: f"chunk-{uuid.uuid4().hex[:8]}")
    type: ChunkType = ChunkType.TEXT
    content: str = ""          # 텍스트/Markdown(표)/이미지 설명
    page: int = 1
    section: str = ""          # 소속 섹션 제목 (heading 추적)
    is_heading: bool = False
    heading_level: int = 0
    image_b64: str | None = None   # 이미지 청크의 base64 (data URI 포함)
    bbox: tuple | None = None  # (x0, y0, x1, y1, page_width, page_height)
    metadata: dict[str, Any] = field(default_factory=dict)


NUMBERING_RE = re.compile(r"^\d+(\.\d+)*\.?\s")
INDENT_STEP = 15  # px


def _detect_heading(content: str, max_size: float, is_bold: bool) -> tuple[bool, int]:
    """(is_heading, level) 반환"""
    m = NUMBERING_RE.match(content)
    if m:
        prefix = m.group(0).strip().rstrip(".")
        depth = prefix.count(".") + 1
        return True, min(depth + 1, 6)
    if max_size >= 16:
        return True, 1
    if max_size >= 14:
        return True, 2
    if is_bold and len(content) <= 80:
        return True, 3
    return False, 0


def _inside_any_rect(bx0: float, by0: float, bx1: float, by1: float, rects: list) -> bool:
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    return any(r.contains(fitz.Point(cx, cy)) for r in rects)


def parse_pdf(file_bytes: bytes) -> list[ParsedChunk]:
    """
    PDF를 2-Pass로 파싱하여 ParsedChunk 리스트 반환.
    1-Pass: 페이지별 텍스트/표/이미지 원본 추출
    2-Pass: heading 기반 섹션 추적 + 본문 병합
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    raw_items: list[dict] = []

    # ── 1-Pass: 원본 추출 ────────────────────────────────────────────────────
    for page_num, page in enumerate(doc, start=1):
        pw, ph = page.rect.width, page.rect.height
        page_items: list[dict] = []

        # 표 영역 수집 (텍스트 블록 필터링용)
        table_rects: list[fitz.Rect] = []
        try:
            for tab in page.find_tables().tables:
                table_rects.append(fitz.Rect(tab.bbox))
        except Exception:
            pass

        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            btype = block["type"]

            if btype == 0:  # 텍스트 블록
                lines_text: list[str] = []
                max_size = 0.0
                is_bold = False
                x0_vals: list[float] = []

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        if text:
                            lines_text.append(text)
                            if span["size"] > max_size:
                                max_size = span["size"]
                            if span["flags"] & 2**4:
                                is_bold = True
                            x0_vals.append(span["bbox"][0])

                content = " ".join(lines_text).strip()
                if not content:
                    continue

                b = block["bbox"]
                if _inside_any_rect(b[0], b[1], b[2], b[3], table_rects):
                    continue

                block_x0 = min(x0_vals) if x0_vals else b[0]
                is_heading, level = _detect_heading(content, max_size, is_bold)
                page_items.append({
                    "type": "text",
                    "content": content,
                    "page": page_num,
                    "bbox": (b[0], b[1], b[2], b[3], pw, ph),
                    "metadata": {"font_size": max_size, "bold": is_bold, "x0": block_x0},
                    "is_heading": is_heading,
                    "level": level,
                })

            elif btype == 1:  # 이미지 블록
                b = block["bbox"]
                bw, bh = b[2] - b[0], b[3] - b[1]
                # 장식선 필터
                if bh < 4 or (bw * bh) < 500 or (bw > 0 and bh / bw < 0.03):
                    continue

                image_b64 = ""
                try:
                    img_info = block.get("image")
                    xref = None
                    if isinstance(img_info, dict):
                        xref = img_info.get("xref")
                    else:
                        for img in page.get_images(full=True):
                            img_rect = page.get_image_rects(img[0])
                            if img_rect and fitz.Rect(img_rect[0]).intersects(fitz.Rect(b)):
                                xref = img[0]
                                break
                    if xref:
                        base_image = doc.extract_image(xref)
                        b64 = base64.b64encode(base_image["image"]).decode()
                        ext = base_image.get("ext", "png")
                        image_b64 = f"data:image/{ext};base64,{b64}"
                except Exception:
                    pass

                page_items.append({
                    "type": "image",
                    "content": "",
                    "image_b64": image_b64,
                    "page": page_num,
                    "bbox": (b[0], b[1], b[2], b[3], pw, ph),
                })

        # 표 파싱 (GFM Markdown)
        try:
            for tab in page.find_tables().tables:
                rows = tab.extract()
                md_rows: list[str] = []
                for i, row in enumerate(rows):
                    cells = [str(c or "").replace("\n", " ") for c in row]
                    md_rows.append("| " + " | ".join(cells) + " |")
                    if i == 0:
                        md_rows.append("|" + "|".join(["---"] * len(cells)) + "|")
                tb = tab.bbox
                page_items.append({
                    "type": "table",
                    "content": "\n".join(md_rows),
                    "page": page_num,
                    "bbox": (tb[0], tb[1], tb[2], tb[3], pw, ph),
                })
        except Exception:
            pass

        # y0 기준 정렬
        page_items.sort(key=lambda o: o["bbox"][1])
        raw_items.extend(page_items)

    doc.close()

    # ── 2-Pass: 섹션 추적 + 본문 병합 ───────────────────────────────────────
    body_x0s = [
        it["metadata"]["x0"]
        for it in raw_items
        if it["type"] == "text" and not it.get("is_heading") and it.get("metadata", {}).get("x0") is not None
    ]
    if len(body_x0s) >= 4:
        base_x0 = sorted(body_x0s)[len(body_x0s) // 4]
    elif body_x0s:
        base_x0 = min(body_x0s)
    else:
        base_x0 = 0.0

    def _estimate_ilvl(x0: float) -> int:
        diff = x0 - base_x0
        if diff < INDENT_STEP:
            return 0
        return min(int(diff // INDENT_STEP), 4)

    chunks: list[ParsedChunk] = []
    current_section = ""
    body_buf: list[tuple[str, int, tuple | None]] = []  # (text, page, bbox)

    def _flush_body():
        if not body_buf:
            return
        merged = "\n".join(t for t, _, _ in body_buf)
        page = body_buf[0][1]
        # 모든 블록의 bbox를 union하여 실제 텍스트 전체 영역 커버
        valid = [b for _, _, b in body_buf if b is not None]
        if valid and len(valid[0]) == 6:
            pw, ph = valid[0][4], valid[0][5]
            union_bbox: tuple = (
                min(b[0] for b in valid),
                min(b[1] for b in valid),
                max(b[2] for b in valid),
                max(b[3] for b in valid),
                pw, ph,
            )
        else:
            union_bbox = body_buf[0][2]  # type: ignore[assignment]
        chunks.append(ParsedChunk(
            type=ChunkType.TEXT,
            content=merged,
            page=page,
            section=current_section,
            bbox=union_bbox,
        ))
        body_buf.clear()

    for it in raw_items:
        if it["type"] == "text":
            if it.get("is_heading"):
                _flush_body()
                current_section = it["content"]
                chunks.append(ParsedChunk(
                    type=ChunkType.TEXT,
                    content=it["content"],
                    page=it["page"],
                    section=current_section,
                    is_heading=True,
                    heading_level=it["level"],
                    bbox=it.get("bbox"),
                    metadata={"tag": f"h{it['level']}"},
                ))
            else:
                x0 = it["metadata"].get("x0", it["bbox"][0])
                ilvl = _estimate_ilvl(x0)
                text = ("  " * ilvl + "- " + it["content"]) if ilvl > 0 else it["content"]
                body_buf.append((text, it["page"], it.get("bbox")))

        elif it["type"] == "image":
            _flush_body()
            chunks.append(ParsedChunk(
                type=ChunkType.IMAGE,
                content="",
                page=it["page"],
                section=current_section,
                image_b64=it.get("image_b64", ""),
                bbox=it.get("bbox"),
            ))

        elif it["type"] == "table":
            _flush_body()
            chunks.append(ParsedChunk(
                type=ChunkType.TABLE,
                content=it["content"],
                page=it["page"],
                section=current_section,
                bbox=it.get("bbox"),
            ))

    _flush_body()
    return chunks
