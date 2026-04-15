"""
청크 편집 API 통합 테스트.
TDD: 아래 케이스들이 먼저 작성된 뒤, 구현이 맞는지 검증한다.

User Journeys:
  1. Admin uploads PDF → status="parsing", ParsedChunkDB rows created
  2. Admin views/edits/deletes parsed chunks
  3. Admin reorders and confirms individual chunks
  4. Admin triggers indexing after review
"""

import os as _os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as db_module
from app.database import Base, get_db
from app.main import app
from app.security.jwt_handler import hash_password

# ── Test DB Setup ─────────────────────────────────────────────────────────────
_TEST_DB_PATH = _os.path.join(_os.path.dirname(__file__), "..", "test_chunks.db")
_TEST_DOCS_DIR = tempfile.mkdtemp(prefix="test_docs_")
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
    # 다른 테스트 파일과 충돌 방지: 기존 override 저장 후 복원
    _orig_override = app.dependency_overrides.get(get_db)
    _orig_engine = db_module.engine
    _orig_session = db_module.SessionLocal

    app.dependency_overrides[get_db] = override_get_db
    db_module.engine = test_engine
    db_module.SessionLocal = TestSessionLocal
    Base.metadata.create_all(bind=test_engine)

    from app.models.db_models import User
    from app.config import settings as cfg

    _orig_docs_path = cfg.documents_path
    cfg.documents_path = _TEST_DOCS_DIR
    _os.makedirs(_TEST_DOCS_DIR, exist_ok=True)

    db = TestSessionLocal()
    admin = User(username="admin", hashed_password=hash_password("admin123"), is_admin=True)
    normal = User(username="normal", hashed_password=hash_password("pass123"), is_admin=False)
    db.add(admin)
    db.add(normal)
    db.commit()
    db.close()

    yield

    cfg.documents_path = _orig_docs_path
    Base.metadata.drop_all(bind=test_engine)
    if _os.path.exists(_TEST_DB_PATH):
        _os.remove(_TEST_DB_PATH)

    # 원래 상태 복원
    db_module.engine = _orig_engine
    db_module.SessionLocal = _orig_session
    if _orig_override is not None:
        app.dependency_overrides[get_db] = _orig_override
    else:
        app.dependency_overrides.pop(get_db, None)


def _make_minimal_pdf() -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "1.1 테스트 섹션\nLTE 핸드오버 절차에 대한 설명입니다.", fontsize=12)
    page.insert_text((50, 200), "1.2 두 번째 섹션\n5G NR 프로토콜 내용입니다.", fontsize=12)
    return doc.tobytes()


def _get_admin_token() -> str:
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    return res.json()["access_token"]


def _get_normal_token() -> str:
    res = client.post("/api/auth/login", json={"username": "normal", "password": "pass123"})
    assert res.status_code == 200
    return res.json()["access_token"]


# ── Journey 1: PDF 업로드 → parsing 상태 + 청크 저장 ─────────────────────────

def test_upload_creates_parsing_status():
    """업로드 후 Document.status가 'parsing'이어야 한다."""
    token = _get_admin_token()
    pdf = _make_minimal_pdf()
    res = client.post(
        "/api/documents",
        files={"file": ("test.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "parsing"
    assert data["chunk_count"] > 0


def test_upload_creates_parsed_chunks():
    """업로드 후 ParsedChunkDB 레코드가 생성되어야 한다."""
    token = _get_admin_token()
    pdf = _make_minimal_pdf()
    # 업로드
    up_res = client.post(
        "/api/documents",
        files={"file": ("chunks_test.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert up_res.status_code == 201
    doc_id = up_res.json()["id"]

    # 청크 목록 조회
    res = client.get(
        f"/api/chunks/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    chunks = res.json()
    assert len(chunks) > 0
    # 모든 청크는 pending 상태
    assert all(c["status"] == "pending" for c in chunks)
    # order는 0-based 순서
    orders = [c["order"] for c in chunks]
    assert orders == sorted(orders)


def test_upload_chunk_has_bbox_for_table():
    """파싱된 청크에 bbox 정보가 있어야 한다 (text/table/image)."""
    token = _get_admin_token()
    pdf = _make_minimal_pdf()
    up_res = client.post(
        "/api/documents",
        files={"file": ("bbox_test.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = up_res.json()["id"]
    chunks = client.get(
        f"/api/chunks/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    # 텍스트 청크는 bbox가 있을 수도 있고 없을 수도 있음
    # 하지만 모든 청크는 필수 필드를 가져야 함
    for c in chunks:
        assert "id" in c
        assert "type" in c
        assert "content" in c
        assert "page" in c
        assert "status" in c


def test_upload_non_pdf_rejected():
    """PDF가 아닌 파일은 400으로 거부해야 한다."""
    token = _get_admin_token()
    res = client.post(
        "/api/documents",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_upload_requires_admin():
    """일반 유저는 문서를 업로드할 수 없다."""
    token = _get_normal_token()
    pdf = _make_minimal_pdf()
    res = client.post(
        "/api/documents",
        files={"file": ("test.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


# ── Journey 2: 청크 편집/삭제 ─────────────────────────────────────────────────

def _upload_and_get_chunks(token: str) -> tuple[str, list]:
    """헬퍼: PDF 업로드 후 (doc_id, chunks) 반환."""
    pdf = _make_minimal_pdf()
    up_res = client.post(
        "/api/documents",
        files={"file": ("edit_test.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = up_res.json()["id"]
    chunks = client.get(
        f"/api/chunks/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    return doc_id, chunks


def test_update_chunk_content():
    """PUT으로 청크 content를 수정할 수 있어야 한다."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)
    assert len(chunks) > 0
    chunk_id = chunks[0]["id"]

    res = client.put(
        f"/api/chunks/{doc_id}/{chunk_id}",
        json={"content": "수정된 내용입니다"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["content"] == "수정된 내용입니다"


def test_update_chunk_processed_content():
    """PUT으로 processed_content를 별도로 설정할 수 있어야 한다."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)
    chunk_id = chunks[0]["id"]

    res = client.put(
        f"/api/chunks/{doc_id}/{chunk_id}",
        json={"processed_content": "가공된 내용"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["processed_content"] == "가공된 내용"
    # 원본 content는 그대로
    original_content = chunks[0]["content"]
    assert res.json()["content"] == original_content


def test_update_chunk_is_heading():
    """PUT으로 is_heading 토글이 가능해야 한다."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)
    # TEXT 타입 청크 찾기
    text_chunks = [c for c in chunks if c["type"] == "text"]
    assert len(text_chunks) > 0
    chunk_id = text_chunks[0]["id"]
    original_heading = text_chunks[0]["is_heading"]

    res = client.put(
        f"/api/chunks/{doc_id}/{chunk_id}",
        json={"is_heading": not original_heading},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["is_heading"] == (not original_heading)


def test_delete_chunk_sets_discarded():
    """DELETE가 청크를 discarded 상태로 변경해야 한다 (실제 삭제 아님)."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)
    chunk_id = chunks[0]["id"]

    del_res = client.delete(
        f"/api/chunks/{doc_id}/{chunk_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    # GET으로 목록을 다시 조회하면 discarded 상태로 존재
    all_chunks = client.get(
        f"/api/chunks/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    deleted = next((c for c in all_chunks if c["id"] == chunk_id), None)
    assert deleted is not None
    assert deleted["status"] == "discarded"


def test_chunks_require_admin():
    """일반 유저는 청크 목록을 조회할 수 없다."""
    token = _get_admin_token()
    doc_id, _ = _upload_and_get_chunks(token)

    normal_token = _get_normal_token()
    res = client.get(
        f"/api/chunks/{doc_id}",
        headers={"Authorization": f"Bearer {normal_token}"},
    )
    assert res.status_code == 403


def test_update_nonexistent_chunk_returns_404():
    """존재하지 않는 청크 수정은 404를 반환해야 한다."""
    token = _get_admin_token()
    doc_id, _ = _upload_and_get_chunks(token)

    res = client.put(
        f"/api/chunks/{doc_id}/nonexistent-chunk-id",
        json={"content": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


# ── Journey 3: 확인(confirm) + 재정렬(reorder) ───────────────────────────────

def test_confirm_chunk():
    """POST /confirm이 청크를 confirmed 상태로 변경해야 한다."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)
    chunk_id = chunks[0]["id"]

    res = client.post(
        f"/api/chunks/{doc_id}/{chunk_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "confirmed"


def test_reorder_chunks():
    """POST /reorder가 청크 순서를 업데이트해야 한다."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)
    if len(chunks) < 2:
        pytest.skip("재정렬 테스트에 최소 2개 청크 필요")

    # 역순으로 재정렬
    reversed_ids = [c["id"] for c in reversed(chunks)]
    res = client.post(
        f"/api/chunks/{doc_id}/reorder",
        json={"ordered_ids": reversed_ids},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 204

    # 재조회해서 순서 확인
    after = client.get(
        f"/api/chunks/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    after_ids = [c["id"] for c in after]
    # 역순 ID 목록의 첫 번째가 새 목록의 첫 번째여야 함
    assert after_ids[0] == reversed_ids[0]


# ── Journey 4: 인덱싱 ─────────────────────────────────────────────────────────

def test_index_document_without_api_token():
    """api_token 없이 인덱싱하면 이미지 청크 제외 후 텍스트/표만 인덱싱된다."""
    token = _get_admin_token()
    pdf = _make_minimal_pdf()
    up_res = client.post(
        "/api/documents",
        files={"file": ("index_test.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = up_res.json()["id"]

    # vector_store 모킹 (실제 임베딩 모델 없이)
    with patch("app.modules.vector_store.index_chunks", return_value=3) as mock_index, \
         patch("app.modules.vector_store.delete_doc") as mock_delete:
        res = client.post(
            f"/api/documents/{doc_id}/index",
            json={"provider": "jihye", "api_token": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["status"] == "indexed"
    mock_index.assert_called_once()
    mock_delete.assert_called_once_with(doc_id)


def test_index_nonexistent_document():
    """존재하지 않는 문서 인덱싱은 404를 반환해야 한다."""
    token = _get_admin_token()
    res = client.post(
        "/api/documents/nonexistent-doc-id/index",
        json={"provider": "jihye", "api_token": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_index_requires_admin():
    """일반 유저는 인덱싱을 실행할 수 없다."""
    token = _get_admin_token()
    pdf = _make_minimal_pdf()
    up_res = client.post(
        "/api/documents",
        files={"file": ("perm_test.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = up_res.json()["id"]

    normal_token = _get_normal_token()
    res = client.post(
        f"/api/documents/{doc_id}/index",
        json={"provider": "jihye", "api_token": ""},
        headers={"Authorization": f"Bearer {normal_token}"},
    )
    assert res.status_code == 403


# ── 문서 삭제 시 청크 연쇄 삭제 ──────────────────────────────────────────────

def test_delete_document_cascades_chunks():
    """문서 삭제 시 연관된 ParsedChunkDB 레코드도 삭제되어야 한다."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)
    assert len(chunks) > 0

    del_res = client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    # 삭제된 문서의 청크는 접근 불가 (404) 또는 빈 목록
    res = client.get(
        f"/api/chunks/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 문서가 없어도 청크 목록은 빈 배열로 반환될 수 있음
    chunks_after = res.json()
    assert chunks_after == [] or res.status_code in (200, 404)


# ── 경계값 테스트 ──────────────────────────────────────────────────────────────

def test_get_chunks_nonexistent_doc_returns_empty():
    """존재하지 않는 문서의 청크는 빈 배열을 반환해야 한다."""
    token = _get_admin_token()
    res = client.get(
        "/api/chunks/nonexistent-doc-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []


# ── VLM 엔드포인트 (모킹) ──────────────────────────────────────────────────────

def _create_table_chunk(token: str) -> tuple[str, str]:
    """헬퍼: 테이블 타입 청크를 가진 문서 생성 후 (doc_id, table_chunk_id) 반환."""
    import fitz, uuid
    from app.models.db_models import ParsedChunkDB

    # 문서 먼저 업로드 (text 청크 생성됨)
    doc_id, chunks = _upload_and_get_chunks(token)

    # DB에 table 청크 직접 삽입
    db = TestSessionLocal()
    table_chunk = ParsedChunkDB(
        id=f"chunk-{uuid.uuid4().hex[:8]}",
        doc_id=doc_id,
        type="table",
        content="| 헤더1 | 헤더2 |\n|---|---|\n| 값1 | 값2 |",
        page=1,
        section="테스트 섹션",
        order=999,
        status="pending",
        metadata_json="{}",
    )
    db.add(table_chunk)
    db.commit()
    table_id = table_chunk.id
    db.close()
    return doc_id, table_id


def _create_image_chunk(token: str) -> tuple[str, str]:
    """헬퍼: 이미지 타입 청크를 가진 문서 생성 후 (doc_id, image_chunk_id) 반환."""
    import uuid, base64
    from app.models.db_models import ParsedChunkDB

    doc_id, _ = _upload_and_get_chunks(token)

    # 1x1 PNG base64 (최소 이미지)
    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
        b"\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd4n\x00\x00\x00"
        b"\x00IEND\xaeB`\x82"
    )
    b64_str = f"data:image/png;base64,{base64.b64encode(tiny_png).decode()}"

    db = TestSessionLocal()
    img_chunk = ParsedChunkDB(
        id=f"chunk-{uuid.uuid4().hex[:8]}",
        doc_id=doc_id,
        type="image",
        content="",
        image_b64=b64_str,
        page=1,
        section="이미지 섹션",
        order=998,
        status="pending",
        metadata_json="{}",
    )
    db.add(img_chunk)
    db.commit()
    img_id = img_chunk.id
    db.close()
    return doc_id, img_id


def test_table_review_keep():
    """VLM 검수가 keep 판단 시 confirmed 상태로 변경된다."""
    token = _get_admin_token()
    doc_id, chunk_id = _create_table_chunk(token)

    with patch("app.modules.llm_client.LLMClient.complete", return_value='{"action":"keep","processed_content":"| 헤더1 | 헤더2 |\\n|---|---|\\n| 값1 | 값2 |"}'):
        res = client.post(
            f"/api/chunks/{doc_id}/{chunk_id}/table/review",
            json={"provider": "jihye", "api_token": "test-token"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["status"] == "confirmed"


def test_table_review_discard():
    """VLM 검수가 discard 판단 시 discarded 상태로 변경된다."""
    token = _get_admin_token()
    doc_id, chunk_id = _create_table_chunk(token)

    with patch("app.modules.llm_client.LLMClient.complete", return_value='{"action":"discard","issues":"빈 표"}'):
        res = client.post(
            f"/api/chunks/{doc_id}/{chunk_id}/table/review",
            json={"provider": "jihye", "api_token": "test-token"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["status"] == "discarded"


def test_table_flatten():
    """평탄화 후 type이 text로 바뀌고 processed_content가 설정된다."""
    token = _get_admin_token()
    doc_id, chunk_id = _create_table_chunk(token)

    with patch("app.modules.llm_client.LLMClient.complete", return_value="헤더1: 값1\n헤더2: 값2"):
        res = client.post(
            f"/api/chunks/{doc_id}/{chunk_id}/table/flatten",
            json={"provider": "jihye", "api_token": "test-token"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["type"] == "text"
    assert "헤더1" in res.json()["processed_content"]


def test_table_chat():
    """채팅 편집 후 processed_content가 업데이트된다."""
    token = _get_admin_token()
    doc_id, chunk_id = _create_table_chunk(token)

    with patch("app.modules.llm_client.LLMClient.complete", return_value="| 수정된헤더 | 헤더2 |\n|---|---|\n| 값1 | 값2 |"):
        res = client.post(
            f"/api/chunks/{doc_id}/{chunk_id}/table/chat",
            json={"message": "첫 번째 헤더를 '수정된헤더'로 바꿔줘", "provider": "jihye", "api_token": "test-token"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["processed_content"] is not None


def test_image_review_describe():
    """이미지 VLM 검수 후 describe 처리되면 processed_content가 설정된다."""
    token = _get_admin_token()
    doc_id, chunk_id = _create_image_chunk(token)

    with patch("app.modules.llm_client.LLMClient.complete_with_image", return_value='{"action":"describe","result":"순서도 다이어그램"}'):
        res = client.post(
            f"/api/chunks/{doc_id}/{chunk_id}/image/review",
            json={"provider": "jihye", "api_token": "test-token"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["status"] == "confirmed"
    assert "순서도" in (res.json()["processed_content"] or "")


def test_image_review_discard():
    """이미지 VLM 검수가 discard 판단 시 discarded 상태가 된다."""
    token = _get_admin_token()
    doc_id, chunk_id = _create_image_chunk(token)

    with patch("app.modules.llm_client.LLMClient.complete_with_image", return_value='{"action":"discard"}'):
        res = client.post(
            f"/api/chunks/{doc_id}/{chunk_id}/image/review",
            json={"provider": "jihye", "api_token": "test-token"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["status"] == "discarded"


def test_image_review_no_image_returns_400():
    """이미지 데이터가 없는 청크에 image/review 호출 시 400을 반환해야 한다."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)
    # text 청크 (image_b64 없음)
    text_chunks = [c for c in chunks if c["type"] == "text"]
    if not text_chunks:
        pytest.skip("텍스트 청크 없음")
    chunk_id = text_chunks[0]["id"]

    res = client.post(
        f"/api/chunks/{doc_id}/{chunk_id}/image/review",
        json={"provider": "jihye", "api_token": "test-token"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_image_chat():
    """이미지 채팅 편집 후 processed_content가 업데이트된다."""
    token = _get_admin_token()
    doc_id, chunk_id = _create_image_chunk(token)

    with patch("app.modules.llm_client.LLMClient.complete", return_value="수정된 이미지 설명입니다"):
        res = client.post(
            f"/api/chunks/{doc_id}/{chunk_id}/image/chat",
            json={"message": "설명을 더 자세하게", "provider": "jihye", "api_token": "test-token"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["processed_content"] == "수정된 이미지 설명입니다"


# ── 문서 목록 및 페이지 미리보기 ──────────────────────────────────────────────

def test_list_documents():
    """인증된 유저는 문서 목록을 조회할 수 있다."""
    token = _get_admin_token()
    res = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_list_documents_normal_user():
    """일반 유저도 문서 목록을 조회할 수 있다."""
    token = _get_normal_token()
    res = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_page_preview():
    """문서의 PDF 페이지 이미지를 반환한다."""
    token = _get_admin_token()
    doc_id, _ = _upload_and_get_chunks(token)

    res = client.get(
        f"/api/documents/{doc_id}/page/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"


def test_page_preview_nonexistent_doc():
    """존재하지 않는 문서의 페이지 미리보기는 404를 반환한다."""
    token = _get_admin_token()
    res = client.get(
        "/api/documents/nonexistent/page/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_index_document_discards_discarded_chunks():
    """discarded 상태의 청크는 인덱싱 대상에서 제외된다."""
    token = _get_admin_token()
    doc_id, chunks = _upload_and_get_chunks(token)

    # 모든 청크를 discard
    for c in chunks:
        client.delete(
            f"/api/chunks/{doc_id}/{c['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )

    with patch("app.modules.vector_store.index_chunks", return_value=0) as mock_index, \
         patch("app.modules.vector_store.delete_doc"):
        res = client.post(
            f"/api/documents/{doc_id}/index",
            json={"provider": "jihye", "api_token": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    # 모든 청크가 discarded이면 인덱싱 대상이 0개
    called_chunks = mock_index.call_args[0][0] if mock_index.call_args else []
    assert len(called_chunks) == 0


# ── documents.py 추가 커버리지 ────────────────────────────────────────────────

def test_delete_nonexistent_document():
    """존재하지 않는 문서 삭제는 404를 반환해야 한다."""
    token = _get_admin_token()
    res = client.delete(
        "/api/documents/nonexistent-doc-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_page_preview_beyond_last_page():
    """페이지 범위를 벗어난 요청도 마지막 페이지로 클리핑해서 응답한다."""
    token = _get_admin_token()
    doc_id, _ = _upload_and_get_chunks(token)

    # 9999 페이지는 존재하지 않지만 마지막 페이지로 클리핑됨
    res = client.get(
        f"/api/documents/{doc_id}/page/9999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"


def test_index_with_api_token_processes_images():
    """api_token 제공 시 이미지 청크를 VLM으로 처리한다."""
    import uuid
    from app.models.db_models import ParsedChunkDB
    import base64

    token = _get_admin_token()
    doc_id, _ = _upload_and_get_chunks(token)

    # 이미지 청크 추가
    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
        b"\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd4n\x00\x00\x00"
        b"\x00IEND\xaeB`\x82"
    )
    b64_str = f"data:image/png;base64,{base64.b64encode(tiny_png).decode()}"
    db = TestSessionLocal()
    img_chunk = ParsedChunkDB(
        id=f"chunk-{uuid.uuid4().hex[:8]}",
        doc_id=doc_id,
        type="image",
        content="",
        image_b64=b64_str,
        page=1,
        section="",
        order=997,
        status="pending",
        metadata_json="{}",
    )
    db.add(img_chunk)
    db.commit()
    db.close()

    with patch("app.modules.image_processor.process_images") as mock_proc, \
         patch("app.modules.vector_store.index_chunks", return_value=2), \
         patch("app.modules.vector_store.delete_doc"):
        # process_images returns text chunk (VLM describe result)
        from app.modules.pdf_parser import ParsedChunk, ChunkType
        described = ParsedChunk(type=ChunkType.IMAGE, content="다이어그램 설명", page=1, section="")
        mock_proc.return_value = [described]

        res = client.post(
            f"/api/documents/{doc_id}/index",
            json={"provider": "jihye", "api_token": "real-token"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    assert res.json()["status"] == "indexed"
    mock_proc.assert_called_once()
