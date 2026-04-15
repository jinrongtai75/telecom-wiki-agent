"""
MDExporter + SummaryGenerator + NoiseRemover.find_candidates 테스트.

TDD User Journeys:
  1. MDExporter가 ParsedChunkDB 목록을 올바른 Markdown으로 변환한다
  2. discarded 청크는 MD에 포함되지 않는다
  3. summary/heading/table/image 타입이 각각 올바른 형식으로 렌더링된다
  4. find_candidates가 반복 텍스트를 노이즈 후보로 탐지한다
  5. SummaryGenerator가 heading 이후 본문을 요약해서 SUMMARY 청크를 삽입한다
  6. /api/documents/{doc_id}/summarize 엔드포인트가 SUMMARY 청크를 삽입한다
  7. /api/documents/{doc_id}/noise/candidates 엔드포인트가 후보 목록을 반환한다
  8. /api/documents/{doc_id}/markdown 엔드포인트가 저장된 MD를 반환한다
"""

import os as _os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as db_module
from app.database import Base, get_db
from app.main import app
from app.models.db_models import Document, ParsedChunkDB, User
from app.modules.md_exporter import MDExporter
from app.modules.noise_remover import find_candidates
from app.modules.pdf_parser import ChunkType, ParsedChunk
from app.security.jwt_handler import hash_password

# ── Test DB Setup ─────────────────────────────────────────────────────────────
_TEST_DB_PATH = _os.path.join(_os.path.dirname(__file__), "..", "test_md.db")
_TEST_DOCS_DIR = tempfile.mkdtemp(prefix="test_docs_md_")
_TEST_MARKDOWNS_DIR = tempfile.mkdtemp(prefix="test_markdowns_")
TEST_DB_URL = f"sqlite:///{_TEST_DB_PATH}"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

client = TestClient(app)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True, scope="module")
def setup_test_db():
    _orig_override = app.dependency_overrides.get(get_db)
    _orig_engine = db_module.engine
    _orig_session = db_module.SessionLocal

    app.dependency_overrides[get_db] = override_get_db
    db_module.engine = test_engine
    db_module.SessionLocal = TestSessionLocal
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)
    if _orig_override is not None:
        app.dependency_overrides[get_db] = _orig_override
    else:
        app.dependency_overrides.pop(get_db, None)
    db_module.engine = _orig_engine
    db_module.SessionLocal = _orig_session
    if _os.path.exists(_TEST_DB_PATH):
        _os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def admin_token():
    db = TestSessionLocal()
    try:
        user = User(
            username="mdtestadmin",
            hashed_password=hash_password("password123"),
            is_admin=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
    resp = client.post("/api/auth/login", json={"username": "mdtestadmin", "password": "password123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def make_chunks(doc_id: str) -> list[ParsedChunkDB]:
    """테스트용 ParsedChunkDB 목록 생성."""
    chunks = [
        ParsedChunkDB(
            id="c1", doc_id=doc_id, type="text", content="1. Introduction",
            page=1, section="", order=0, is_heading=True, heading_level=1,
            status="confirmed", metadata_json="{}",
        ),
        ParsedChunkDB(
            id="c2", doc_id=doc_id, type="summary", content="이 섹션은 소개입니다.",
            page=1, section="1. Introduction", order=1, is_heading=False, heading_level=0,
            status="confirmed", metadata_json="{}",
        ),
        ParsedChunkDB(
            id="c3", doc_id=doc_id, type="text", content="This is the body text.",
            page=1, section="1. Introduction", order=2, is_heading=False, heading_level=0,
            status="confirmed", metadata_json="{}",
        ),
        ParsedChunkDB(
            id="c4", doc_id=doc_id, type="table", content="| A | B |\n|---|---|\n| 1 | 2 |",
            page=2, section="1. Introduction", order=3, is_heading=False, heading_level=0,
            status="confirmed", metadata_json="{}",
        ),
        ParsedChunkDB(
            id="c5", doc_id=doc_id, type="image", content="이미지 설명",
            image_path="/images/test.png", page=2, section="", order=4,
            is_heading=False, heading_level=0, status="confirmed", metadata_json="{}",
        ),
        ParsedChunkDB(
            id="c6", doc_id=doc_id, type="text", content="discarded text",
            page=3, section="", order=5, is_heading=False, heading_level=0,
            status="discarded", metadata_json="{}",
        ),
    ]
    return chunks


# ── Unit Tests: MDExporter ────────────────────────────────────────────────────


def test_md_exporter_basic():
    """MDExporter가 청크 목록을 Markdown 문자열로 변환한다."""
    exporter = MDExporter()
    chunks = make_chunks("doc-001")
    md = exporter.export_from_db_chunks(chunks, "doc-001", "test.pdf")

    assert "# 1. Introduction" in md
    assert "> **요약**: 이 섹션은 소개입니다." in md
    assert "This is the body text." in md
    assert "| A | B |" in md
    assert "![image](/images/test.png)" in md
    assert "이미지 설명" in md


def test_md_exporter_excludes_discarded():
    """discarded 상태 청크는 MD에 포함되지 않는다."""
    exporter = MDExporter()
    chunks = make_chunks("doc-002")
    md = exporter.export_from_db_chunks(chunks, "doc-002", "test.pdf")
    assert "discarded text" not in md


def test_md_exporter_heading_levels():
    """heading_level에 따라 올바른 # 마크다운 헤딩이 생성된다."""
    exporter = MDExporter()
    chunks = [
        ParsedChunkDB(
            id="h1", doc_id="d", type="text", content="H1",
            page=1, section="", order=0, is_heading=True, heading_level=1,
            status="confirmed", metadata_json="{}",
        ),
        ParsedChunkDB(
            id="h2", doc_id="d", type="text", content="H2",
            page=1, section="", order=1, is_heading=True, heading_level=2,
            status="confirmed", metadata_json="{}",
        ),
        ParsedChunkDB(
            id="h3", doc_id="d", type="text", content="H3",
            page=1, section="", order=2, is_heading=True, heading_level=3,
            status="confirmed", metadata_json="{}",
        ),
    ]
    md = exporter.export_from_db_chunks(chunks, "d", "test.pdf")
    assert "# H1" in md
    assert "## H2" in md
    assert "### H3" in md


def test_md_exporter_save_and_load(tmp_path):
    """MD 파일 저장 및 읽기."""
    exporter = MDExporter()
    chunks = make_chunks("doc-003")
    md = exporter.export_from_db_chunks(chunks, "doc-003", "test.pdf")

    path = str(tmp_path / "test.md")
    exporter.save(md, path)
    loaded = exporter.load(path)
    assert loaded == md


def test_md_exporter_metadata_header():
    """MD 헤더에 doc_id와 source_name이 포함된다."""
    exporter = MDExporter()
    chunks = make_chunks("doc-meta")
    md = exporter.export_from_db_chunks(chunks, "doc-meta", "3GPP_spec.pdf")
    assert "doc:doc-meta" in md
    assert "source:3GPP_spec.pdf" in md


def test_md_exporter_processed_content_preferred():
    """processed_content가 있으면 content 대신 사용된다."""
    exporter = MDExporter()
    chunk = ParsedChunkDB(
        id="pc1", doc_id="d", type="text", content="원본 내용",
        processed_content="편집된 내용",
        page=1, section="", order=0, is_heading=False, heading_level=0,
        status="confirmed", metadata_json="{}",
    )
    md = exporter.export_from_db_chunks([chunk], "d", "test.pdf")
    assert "편집된 내용" in md
    assert "원본 내용" not in md


# ── Unit Tests: find_candidates ───────────────────────────────────────────────


def test_find_candidates_page_numbers():
    """페이지 번호 패턴이 노이즈 후보로 탐지된다."""
    chunks = [
        ParsedChunk(id=f"p{i}", type=ChunkType.TEXT, content=str(i), page=i, section="")
        for i in range(1, 6)
    ]
    candidates = find_candidates(chunks)
    # 각 숫자는 한 번씩만 등장하므로 반복 텍스트는 아니지만 패턴 매칭으로 탐지
    texts = [c.text for c in candidates]
    assert any(t.isdigit() for t in texts)


def test_find_candidates_repeated_text():
    """3회 이상 반복되는 짧은 텍스트가 노이즈 후보로 탐지된다."""
    repeated = "LGU+ Confidential"
    chunks = [
        ParsedChunk(id=f"r{i}", type=ChunkType.TEXT, content=repeated, page=i, section="")
        for i in range(5)
    ]
    chunks.append(
        ParsedChunk(id="body", type=ChunkType.TEXT, content="실제 본문 내용입니다.", page=6, section="")
    )
    candidates = find_candidates(chunks)
    texts = [c.text for c in candidates]
    assert repeated in texts
    assert "실제 본문 내용입니다." not in texts


def test_find_candidates_custom_patterns():
    """커스텀 패턴으로 추가 노이즈 후보를 탐지한다."""
    chunks = [
        ParsedChunk(id="c1", type=ChunkType.TEXT, content="DRAFT v0.1", page=1, section=""),
        ParsedChunk(id="c2", type=ChunkType.TEXT, content="실제 내용", page=2, section=""),
    ]
    candidates = find_candidates(chunks, custom_patterns=[r"^DRAFT"])
    texts = [c.text for c in candidates]
    assert "DRAFT v0.1" in texts


def test_find_candidates_ignores_table_image():
    """TABLE/IMAGE 타입은 노이즈 후보 탐지에서 제외된다."""
    chunks = [
        ParsedChunk(id="t1", type=ChunkType.TABLE, content="| A |\n|---|\n| 1 |", page=1, section=""),
        ParsedChunk(id="i1", type=ChunkType.IMAGE, content="", page=1, section="", image_b64="data:image/png;base64,abc"),
    ]
    candidates = find_candidates(chunks)
    assert candidates == []


# ── Unit Tests: SummaryGenerator ─────────────────────────────────────────────


def test_summary_generator_inserts_chunks(admin_token):
    """SummaryGenerator가 heading 이후 SUMMARY 청크를 삽입한다."""
    import uuid as _uuid
    db = TestSessionLocal()

    # 문서 + 청크 생성
    from app.models.db_models import User as DBUser
    user = db.query(DBUser).filter(DBUser.username == "mdtestadmin").first()
    doc = Document(
        filename="sumtest.pdf", original_name="sumtest.pdf",
        file_size=100, status="parsing", uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    pfx = _uuid.uuid4().hex[:6]

    chunks_data = [
        ParsedChunkDB(
            id=f"{pfx}-s1", doc_id=doc.id, type="text", content="2. Background",
            page=1, section="", order=0, is_heading=True, heading_level=2,
            status="confirmed", metadata_json="{}",
        ),
        ParsedChunkDB(
            id=f"{pfx}-s2", doc_id=doc.id, type="text", content="Background content here.",
            page=1, section="2. Background", order=1, is_heading=False, heading_level=0,
            status="confirmed", metadata_json="{}",
        ),
    ]
    for c in chunks_data:
        db.add(c)
    db.commit()

    db.refresh(chunks_data[0])

    from app.modules.summary_generator import SummaryGenerator
    sg = SummaryGenerator()
    mock_llm = MagicMock()
    mock_llm.complete.return_value = "배경 섹션은 기본 개념을 설명합니다."

    inserted = sg.generate_for_doc(chunks_data, mock_llm, db, doc.id)

    assert inserted == 1
    summary_chunks = db.query(ParsedChunkDB).filter(
        ParsedChunkDB.doc_id == doc.id,
        ParsedChunkDB.type == "summary",
    ).all()
    assert len(summary_chunks) == 1
    assert "배경 섹션" in summary_chunks[0].content

    db.close()


def test_summary_generator_removes_old_summaries(admin_token):
    """기존 summary 청크를 삭제 후 재생성한다."""
    import uuid as _uuid
    db = TestSessionLocal()
    from app.models.db_models import User as DBUser
    user = db.query(DBUser).filter(DBUser.username == "mdtestadmin").first()

    doc = Document(
        filename="sumtest2.pdf", original_name="sumtest2.pdf",
        file_size=100, status="parsing", uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    pfx2 = _uuid.uuid4().hex[:6]

    old_summary = ParsedChunkDB(
        id=f"{pfx2}-old-sum", doc_id=doc.id, type="summary", content="Old summary.",
        page=1, section="", order=1, is_heading=False, heading_level=0,
        status="confirmed", metadata_json="{}",
    )
    heading = ParsedChunkDB(
        id=f"{pfx2}-head2", doc_id=doc.id, type="text", content="3. Methods",
        page=1, section="", order=0, is_heading=True, heading_level=2,
        status="confirmed", metadata_json="{}",
    )
    body = ParsedChunkDB(
        id=f"{pfx2}-body2", doc_id=doc.id, type="text", content="Method details.",
        page=1, section="", order=2, is_heading=False, heading_level=0,
        status="confirmed", metadata_json="{}",
    )
    for c in [old_summary, heading, body]:
        db.add(c)
    db.commit()
    old_sum_id = old_summary.id

    from app.modules.summary_generator import SummaryGenerator
    sg = SummaryGenerator()
    mock_llm = MagicMock()
    mock_llm.complete.return_value = "이 섹션은 연구 방법론을 설명합니다."

    all_chunks = db.query(ParsedChunkDB).filter(
        ParsedChunkDB.doc_id == doc.id,
        ParsedChunkDB.status != "discarded",
    ).all()
    sg.generate_for_doc(all_chunks, mock_llm, db, doc.id)

    summaries = db.query(ParsedChunkDB).filter(
        ParsedChunkDB.doc_id == doc.id,
        ParsedChunkDB.type == "summary",
    ).all()
    # 기존 old-sum은 삭제되고 새 summary 1개만 있어야 함
    assert len(summaries) == 1
    assert summaries[0].id != old_sum_id

    db.close()


# ── Integration Tests: API Endpoints ─────────────────────────────────────────


def _create_doc_with_chunks(db, user_id: str) -> str:
    """테스트용 문서와 청크를 DB에 생성하고 doc_id 반환."""
    import uuid as _uuid
    doc = Document(
        filename="apitest.pdf", original_name="apitest.pdf",
        file_size=1000, status="parsing", uploaded_by=user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    prefix = _uuid.uuid4().hex[:6]

    chunks = [
        ParsedChunkDB(
            id=f"{prefix}-c{i}", doc_id=doc.id, type="text",
            content=f"Heading {i}" if i % 3 == 0 else f"Body text {i}",
            page=i + 1, section="", order=i,
            is_heading=(i % 3 == 0), heading_level=1 if i % 3 == 0 else 0,
            status="pending", metadata_json="{}",
        )
        for i in range(6)
    ]
    for c in chunks:
        db.add(c)
    db.commit()
    return doc.id


def test_summarize_endpoint(admin_token):
    """POST /api/documents/{doc_id}/summarize → SUMMARY 청크 삽입."""
    db = TestSessionLocal()
    user = db.query(User).filter(User.username == "mdtestadmin").first()
    doc_id = _create_doc_with_chunks(db, user.id)
    db.close()

    with patch("app.modules.summary_generator.LLMClient") as _mock_cls:
        pass  # LLMClient는 엔드포인트에서 직접 생성

    with patch("app.modules.summary_generator.SummaryGenerator.generate_for_doc", return_value=2):
        resp = client.post(
            f"/api/documents/{doc_id}/summarize",
            json={"provider": "jihye", "api_token": "test-token"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["inserted"] == 2


def test_noise_candidates_endpoint(admin_token):
    """POST /api/documents/{doc_id}/noise/candidates → 후보 목록 반환."""
    db = TestSessionLocal()
    user = db.query(User).filter(User.username == "mdtestadmin").first()
    doc_id = _create_doc_with_chunks(db, user.id)
    db.close()

    resp = client.post(
        f"/api/documents/{doc_id}/noise/candidates",
        json=[],
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "candidates" in resp.json()
    assert isinstance(resp.json()["candidates"], list)


def test_markdown_endpoint_not_found(admin_token):
    """markdown_path가 없는 문서에 GET /markdown → 404."""
    db = TestSessionLocal()
    user = db.query(User).filter(User.username == "mdtestadmin").first()
    doc_id = _create_doc_with_chunks(db, user.id)
    db.close()

    resp = client.get(
        f"/api/documents/{doc_id}/markdown",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_markdown_endpoint_returns_content(admin_token, tmp_path):
    """markdown_path가 있으면 GET /markdown → MD 내용 반환."""
    from app.services.storage_service import get_storage

    db = TestSessionLocal()
    user = db.query(User).filter(User.username == "mdtestadmin").first()
    doc_id = _create_doc_with_chunks(db, user.id)

    # 스토리지 서비스로 MD 저장 후 Document에 경로 기록
    md_content = "# Test Document\n\nContent here.\n"
    get_storage().save(f"markdowns/{doc_id}.md", md_content.encode("utf-8"))

    doc = db.query(Document).filter(Document.id == doc_id).first()
    doc.markdown_path = f"markdowns/{doc_id}.md"
    db.commit()
    db.close()

    resp = client.get(
        f"/api/documents/{doc_id}/markdown",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "# Test Document" in resp.text
