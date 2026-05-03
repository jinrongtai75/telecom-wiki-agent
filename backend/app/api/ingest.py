"""
MD 파일 인제스트 엔드포인트.
전처리 도구(preprocessor)에서 MD 내보내기 후 이 엔드포인트로 POST하면
md_chunker → vector_store 파이프라인으로 ChromaDB에 적재됩니다.

요청 형식: multipart/form-data
  - filename    : str   (MD 파일명, 예: 3GPP_TS_38.300.md)
  - content     : str   (MD 전체 텍스트)
  - source_name : str   (원본 PDF 파일명, 선택)
  - pdf_file    : File  (원본 PDF 바이너리, 선택 — 검색결과 페이지 미리보기용)
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Document, User
from app.modules import vector_store
from app.modules.md_chunker import md_chunker
from app.security.auth_deps import get_current_user
from app.services.storage_service import LocalStorageService, get_storage

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class IngestMdResponse(BaseModel):
    doc_id: str
    original_name: str
    chunk_count: int
    status: str
    indexed_at: str
    has_pdf: bool


@router.post("/md", response_model=IngestMdResponse, status_code=status.HTTP_201_CREATED)
def ingest_md(
    filename: str = Form(...),
    content: str = Form(...),
    source_name: str = Form(""),
    pdf_file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    전처리 도구에서 내보낸 MD 파일을 수신하여 ChromaDB에 인덱싱.
    - MD 파일을 storage에 documents/{doc_id}.md 키로 저장
    - PDF 첨부 시 storage에 documents/{doc_id}.pdf 키로 저장 (검색결과 미리보기용)
    - md_chunker로 섹션 청킹 → vector_store 임베딩 & 적재
    - Document 레코드 생성 (status='indexed')
    """
    storage = get_storage()

    display_name = source_name or filename
    if not display_name.endswith(".pdf"):
        display_name = display_name.rsplit(".", 1)[0] + ".pdf"

    # 동일 파일명 기존 문서 교체 (재적재 지원)
    existing = db.query(Document).filter(Document.original_name == display_name).first()
    if existing:
        storage.delete(f"documents/{existing.id}.pdf")
        vector_store.delete_doc(existing.id)
        db.delete(existing)
        db.commit()

    # Document 레코드 생성
    doc = Document(
        filename=filename,
        original_name=display_name,
        file_size=len(content.encode("utf-8")),
        status="indexing",
        uploaded_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    has_pdf = False
    try:
        # MD 저장
        storage.save(f"markdowns/{doc.id}.md", content.encode("utf-8"))
        doc.markdown_path = f"markdowns/{doc.id}.md"

        # PDF 저장 (선택) — GET /{doc_id}/page/{n} 미리보기 활성화
        if pdf_file and pdf_file.filename:
            pdf_bytes = pdf_file.file.read()
            storage.save(f"documents/{doc.id}.pdf", pdf_bytes)
            has_pdf = True

        # ChromaDB 인덱싱 (MD 텍스트 직접 전달 — 파일 경유 불필요)
        vector_store.delete_doc(doc.id)
        index_chunks = md_chunker.chunk_from_text(content, doc.id)
        chunk_count = vector_store.index_chunks(index_chunks)

        doc.chunk_count = chunk_count
        doc.status = "indexed"
        doc.indexed_at = datetime.now(UTC)
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = "error"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인덱싱 중 오류: {str(e)}",
        ) from e

    return IngestMdResponse(
        doc_id=doc.id,
        original_name=doc.original_name,
        chunk_count=doc.chunk_count or 0,
        status=doc.status,
        indexed_at=doc.indexed_at.isoformat() if doc.indexed_at else "",
        has_pdf=has_pdf,
    )


@router.post("/reindex-all", status_code=200)
def reindex_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    저장된 MD 파일로 전체 재인덱싱 (임베딩 모델 변경 후 사용).
    관리자 전용. /api/settings/vector-store/reset 실행 후 호출하세요.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자만 실행 가능합니다")

    storage = get_storage()
    docs = db.query(Document).filter(Document.status == "indexed").all()

    reindexed: list[dict] = []
    errors: list[dict] = []

    for doc in docs:
        try:
            if not doc.markdown_path:
                errors.append({"doc_id": doc.id, "name": doc.original_name, "error": "MD 파일 경로 없음"})
                continue

            md_bytes = storage.load(doc.markdown_path)
            content = md_bytes.decode("utf-8")

            vector_store.delete_doc(doc.id)
            index_chunks = md_chunker.chunk_from_text(content, doc.id)
            chunk_count = vector_store.index_chunks(index_chunks)

            doc.chunk_count = chunk_count
            doc.indexed_at = datetime.now(UTC)
            db.commit()

            reindexed.append({"doc_id": doc.id, "name": doc.original_name, "chunks": chunk_count})
        except Exception as e:
            errors.append({"doc_id": doc.id, "name": doc.original_name, "error": str(e)})

    return {
        "reindexed": len(reindexed),
        "errors": len(errors),
        "results": reindexed,
        "error_details": errors,
    }


@router.post("/migrate-storage", status_code=200)
def migrate_storage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    로컬 파일시스템 → Supabase 마이그레이션 + ChromaDB 재인덱싱 (관리자 전용).
    1) ChromaDB 리셋 (Gemini 임베딩으로 재시작)
    2) 각 문서의 MD/PDF를 로컬→Supabase 이전
    3) MD로 ChromaDB 재인덱싱
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자만 실행 가능합니다")

    local = LocalStorageService(base_path="./data")
    cloud = get_storage()
    is_cloud = not isinstance(cloud, LocalStorageService)

    # ChromaDB 리셋 (Gemini 임베딩 공간으로 재초기화)
    vector_store.reset_collection()

    docs = db.query(Document).filter(Document.status == "indexed").all()
    reindexed: list[dict] = []
    pdf_migrated: list[str] = []
    storage_errors: list[dict] = []
    errors: list[dict] = []

    for doc in docs:
        try:
            md_key = f"markdowns/{doc.id}.md"
            md_bytes: bytes | None = None

            # MD: 로컬 우선 → 없으면 클라우드에서 시도
            if local.exists(md_key):
                md_bytes = local.load(md_key)
                if is_cloud:
                    try:
                        cloud.save(md_key, md_bytes)
                    except Exception as se:
                        storage_errors.append({"name": doc.original_name, "key": md_key, "error": str(se)})
            elif is_cloud:
                try:
                    md_bytes = cloud.load(md_key)
                except FileNotFoundError:
                    pass

            if md_bytes is None:
                errors.append({"name": doc.original_name, "error": "MD 파일 없음 — 전처리 에이전트에서 재적재 필요"})
                continue

            # ChromaDB 재인덱싱 (스토리지 이전 실패해도 계속 진행)
            vector_store.delete_doc(doc.id)
            chunks = md_chunker.chunk_from_text(md_bytes.decode("utf-8"), doc.id)
            chunk_count = vector_store.index_chunks(chunks)
            doc.chunk_count = chunk_count
            doc.indexed_at = datetime.now(UTC)
            db.commit()
            reindexed.append({"name": doc.original_name, "chunks": chunk_count})

            # PDF: 로컬에 있고 Supabase에 없으면 이전
            if is_cloud:
                pdf_key = f"documents/{doc.id}.pdf"
                if local.exists(pdf_key) and not cloud.exists(pdf_key):
                    try:
                        cloud.save(pdf_key, local.load(pdf_key))
                        pdf_migrated.append(doc.original_name)
                    except Exception as se:
                        storage_errors.append({"name": doc.original_name, "key": pdf_key, "error": str(se)})

        except Exception as e:
            errors.append({"name": doc.original_name, "error": str(e)})

    return {
        "reindexed": len(reindexed),
        "pdf_migrated": len(pdf_migrated),
        "errors": len(errors),
        "storage_errors": len(storage_errors),
        "results": reindexed,
        "pdf_files": pdf_migrated,
        "error_details": errors,
        "storage_error_details": storage_errors,
    }
