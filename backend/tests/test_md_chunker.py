"""
MDChunker TDD 테스트.

User Journeys:
  1. 기본 섹션 파싱 - heading + body → IndexChunk 생성
  2. summary가 청크 텍스트에 포함된다
  3. 다중 섹션 → 다중 청크
  4. 긴 섹션 → 슬라이딩 윈도우 분할 (prefix 반복 포함)
  5. 표는 섹션 컨텍스트(헤딩)와 함께 별도 청크
  6. 이미지 description이 청크로 포함된다
  7. discarded 청크는 MD에 없으므로 자동 제외
  8. chunk_from_file: 파일 경로로 직접 파싱
  9. 헤딩 없는 서두 본문도 청크로 포함
"""

import tempfile
from pathlib import Path

import pytest

from app.modules.md_chunker import MDChunker

DOC_ID = "test-doc-001"

SAMPLE_MD = """\
<!-- doc:test-doc-001 source:test.pdf created_at:2026-04-14T00:00:00Z -->

<!-- obj:c1 type:text page:1 -->
# 1. Introduction

<!-- obj:c2 type:summary page:1 -->
> **요약**: 이 섹션은 소개입니다.

<!-- obj:c3 type:text page:1 -->
본문 내용입니다. 소개 섹션의 첫 번째 단락입니다.

<!-- obj:c4 type:text page:2 -->
소개 섹션의 두 번째 단락입니다.

<!-- obj:c5 type:table page:2 -->
| 파라미터 | 값 |
|---------|---|
| 대역폭 | 100 MHz |

<!-- obj:c6 type:text page:3 -->
## 2. Background

<!-- obj:c7 type:summary page:3 -->
> **요약**: 배경 섹션은 기본 개념을 설명합니다.

<!-- obj:c8 type:text page:3 -->
배경 내용입니다.

<!-- obj:c9 type:image page:4 -->
![image](/images/test.png)
5G 기지국 블록 다이어그램입니다.
"""


def test_basic_section_creates_chunk():
    """heading + body가 하나의 IndexChunk로 생성된다."""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(SAMPLE_MD, DOC_ID)
    assert len(chunks) > 0
    # 첫 번째 청크는 Introduction 섹션
    intro = next((c for c in chunks if "Introduction" in c.section), None)
    assert intro is not None
    assert "1. Introduction" in intro.content


def test_summary_included_in_chunk():
    """summary가 청크 텍스트 안에 포함된다."""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(SAMPLE_MD, DOC_ID)
    intro = next((c for c in chunks if "Introduction" in c.section), None)
    assert intro is not None
    assert "소개입니다" in intro.content


def test_multiple_sections_multiple_chunks():
    """다중 섹션 → 각 섹션별 청크 생성."""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(SAMPLE_MD, DOC_ID)
    text_chunks = [c for c in chunks if c.chunk_type == "text"]
    sections = {c.section for c in text_chunks}
    assert "1. Introduction" in sections
    assert "2. Background" in sections


def test_table_is_separate_chunk():
    """표는 섹션 컨텍스트와 함께 별도 청크로 생성된다."""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(SAMPLE_MD, DOC_ID)
    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) == 1
    assert "대역폭" in table_chunks[0].content
    assert "Introduction" in table_chunks[0].content  # 섹션 컨텍스트 포함


def test_image_chunk_included():
    """이미지 description이 image 청크로 포함된다."""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(SAMPLE_MD, DOC_ID)
    image_chunks = [c for c in chunks if c.chunk_type == "image"]
    assert len(image_chunks) == 1
    assert "블록 다이어그램" in image_chunks[0].content


def test_chunk_ids_are_unique():
    """모든 청크 ID가 유일하다."""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(SAMPLE_MD, DOC_ID)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_doc_id():
    """모든 청크의 doc_id가 올바르다."""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(SAMPLE_MD, DOC_ID)
    for c in chunks:
        assert c.doc_id == DOC_ID


def test_long_section_sliding_window():
    """긴 섹션은 슬라이딩 윈도우로 분할되고, 각 청크에 heading prefix가 포함된다."""
    # 충분히 긴 본문 생성 (약 600 토큰 분량)
    long_body = " ".join(["longword"] * 600)
    md = f"""\
<!-- doc:d source:t.pdf created_at:2026-01-01T00:00:00Z -->

<!-- obj:h1 type:text page:1 -->
# Long Section

<!-- obj:b1 type:text page:1 -->
{long_body}
"""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(md, "d")
    text_chunks = [c for c in chunks if c.chunk_type == "text"]
    assert len(text_chunks) > 1  # 분할됨
    for c in text_chunks:
        assert "Long Section" in c.content  # prefix 반복


def test_chunk_from_file(tmp_path):
    """chunk_from_file: 파일 경로로 직접 파싱한다."""
    md_file = tmp_path / "test.md"
    md_file.write_text(SAMPLE_MD, encoding="utf-8")
    chunker = MDChunker()
    chunks = chunker.chunk_from_file(str(md_file), DOC_ID)
    assert len(chunks) > 0


def test_preamble_without_heading():
    """헤딩 이전 서두 본문도 청크로 포함된다."""
    md = """\
<!-- doc:d source:t.pdf created_at:2026-01-01T00:00:00Z -->

<!-- obj:pre type:text page:1 -->
문서 전체 개요입니다. 헤딩 없이 시작하는 서두 텍스트.

<!-- obj:h1 type:text page:2 -->
# 1. Introduction
"""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(md, "d")
    text_chunks = [c for c in chunks if c.chunk_type == "text"]
    assert any("서두 텍스트" in c.content for c in text_chunks)


def test_background_summary_in_chunk():
    """Background 섹션 summary가 해당 청크 텍스트에 포함된다."""
    chunker = MDChunker()
    chunks = chunker.chunk_from_text(SAMPLE_MD, DOC_ID)
    bg = next((c for c in chunks if "Background" in c.section and c.chunk_type == "text"), None)
    assert bg is not None
    assert "기본 개념" in bg.content
