import pytest
from app.modules.pdf_parser import ChunkType, parse_pdf
from app.modules.noise_remover import remove_noise
from app.modules.chunker import build_index_chunks


def _make_minimal_pdf() -> bytes:
    """최소 PDF 바이트 생성 (PyMuPDF 테스트용)."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "1.1 테스트 섹션\nLTE 핸드오버 절차에 대한 설명입니다.\n페이지 1", fontsize=12)
    page.insert_text((50, 200), "1.2 또 다른 섹션\n5G NR 프로토콜 관련 내용입니다.", fontsize=12)
    return doc.tobytes()


def test_parse_pdf_returns_chunks():
    pdf_bytes = _make_minimal_pdf()
    chunks = parse_pdf(pdf_bytes)
    assert len(chunks) > 0
    assert all(hasattr(c, "type") for c in chunks)


def test_parse_pdf_chunk_types():
    pdf_bytes = _make_minimal_pdf()
    chunks = parse_pdf(pdf_bytes)
    types = {c.type for c in chunks}
    # 텍스트 청크는 반드시 있어야 함
    assert ChunkType.TEXT in types


def test_noise_remover():
    from app.modules.pdf_parser import ParsedChunk, ChunkType
    chunks = [
        ParsedChunk(type=ChunkType.TEXT, content="1", page=1, section=""),
        ParsedChunk(type=ChunkType.TEXT, content="1", page=2, section=""),
        ParsedChunk(type=ChunkType.TEXT, content="1", page=3, section=""),
        ParsedChunk(type=ChunkType.TEXT, content="실제 내용입니다", page=1, section=""),
    ]
    result = remove_noise(chunks)
    contents = [c.content for c in result]
    assert "1" not in contents  # 3회 반복 제거
    assert "실제 내용입니다" in contents


def test_build_index_chunks():
    pdf_bytes = _make_minimal_pdf()
    chunks = parse_pdf(pdf_bytes)
    chunks = remove_noise(chunks)
    index_chunks = build_index_chunks(chunks, "doc-test-001")
    assert len(index_chunks) > 0
    assert all(c.doc_id == "doc-test-001" for c in index_chunks)
    assert all(c.content for c in index_chunks)
