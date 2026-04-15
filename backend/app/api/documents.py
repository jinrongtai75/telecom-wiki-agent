import json
from datetime import UTC, datetime

import fitz  # PyMuPDF
from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Document, ParsedChunkDB, User
from app.models.schemas import (
    DocumentMeta,
    NoiseCandidateItem,
    NoiseCandidatesResponse,
    SummarizeResponse,
    VlmRequest,
)
from app.modules import image_processor, noise_remover, pdf_parser, vector_store
from app.modules.llm_client import LLMClient
from app.modules.md_chunker import md_chunker
from app.modules.md_exporter import md_exporter
from app.modules.noise_remover import find_candidates
from app.modules.pdf_parser import ChunkType
from app.modules.summary_generator import summary_generator
from app.security.auth_deps import get_current_user, require_admin
from app.services.storage_service import get_storage

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_MIME = {"application/pdf"}

@router.post("", response_model=DocumentMeta, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """PDF 업로드 → 파싱 → ParsedChunkDB 저장 (VLM/인덱싱 없음, 검토 후 /index 호출)"""
    if file.content_type not in ALLOWED_MIME or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF 파일만 업로드 가능합니다",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="파일 크기는 100MB를 초과할 수 없습니다",
        )

    doc = Document(
        filename=file.filename,
        original_name=file.filename,
        file_size=len(file_bytes),
        status="parsing",
        uploaded_by=admin.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 원본 PDF 저장
    get_storage().save(f"documents/{doc.id}.pdf", file_bytes)

    try:
        parsed = pdf_parser.parse_pdf(file_bytes)
        parsed = noise_remover.remove_noise(parsed)

        for order, chunk in enumerate(parsed):
            bbox_json = None
            if chunk.bbox:
                x0, y0, x1, y1, pw, ph = chunk.bbox
                bbox_json = json.dumps({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "pw": pw, "ph": ph})

            db_chunk = ParsedChunkDB(
                id=chunk.id,
                doc_id=doc.id,
                type=chunk.type.value,
                content=chunk.content,
                page=chunk.page,
                section=chunk.section,
                order=order,
                is_heading=chunk.is_heading,
                heading_level=chunk.heading_level,
                image_b64=chunk.image_b64,
                bbox_json=bbox_json,
                status="pending",
                metadata_json=json.dumps(chunk.metadata),
            )
            db.add(db_chunk)

        doc.chunk_count = len(parsed)
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = "error"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문서 파싱 중 오류: {str(e)}",
        ) from e

    return DocumentMeta(
        id=doc.id,
        original_name=doc.original_name,
        file_size=doc.file_size,
        chunk_count=doc.chunk_count,
        status=doc.status,
        uploaded_at=doc.uploaded_at,
        indexed_at=doc.indexed_at,
    )

@router.post("/{doc_id}/index", response_model=DocumentMeta)
def index_document(
    doc_id: str,
    body: VlmRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """편집 완료된 청크를 VLM 처리 후 ChromaDB에 인덱싱."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db_chunks = (
        db.query(ParsedChunkDB)
        .filter(ParsedChunkDB.doc_id == doc_id, ParsedChunkDB.status != "discarded")
        .order_by(ParsedChunkDB.order)
        .all()
    )

    parsed: list[pdf_parser.ParsedChunk] = []
    for c in db_chunks:
        effective_content = c.processed_content if c.processed_content else c.content
        chunk = pdf_parser.ParsedChunk(
            id=c.id,
            type=ChunkType(c.type),
            content=effective_content,
            page=c.page,
            section=c.section,
            is_heading=c.is_heading,
            heading_level=c.heading_level,
            image_b64=c.image_b64,
        )
        if c.image_path:
            chunk.metadata["image_path"] = c.image_path
        parsed.append(chunk)

    try:
        if body.api_token:
            llm = LLMClient(provider=body.provider, api_token=body.api_token)
            result: list[pdf_parser.ParsedChunk] = []
            for chunk in parsed:
                if chunk.type == ChunkType.IMAGE and chunk.image_b64 and not chunk.content:
                    processed_chunks = image_processor.process_images([chunk], llm, doc_id)
                    if processed_chunks:
                        proc = processed_chunks[0]
                        result.append(proc)
                        db_c = db.query(ParsedChunkDB).filter(ParsedChunkDB.id == chunk.id).first()
                        if db_c:
                            db_c.processed_content = proc.content
                            db_c.image_path = proc.metadata.get("image_path")
                            db_c.image_b64 = None
                else:
                    result.append(chunk)
            parsed = result
        else:
            parsed = [c for c in parsed if c.type != ChunkType.IMAGE]

        # ── MD 저장 (진실의 원본) ──────────────────────────────────────────────
        all_db_chunks = (
            db.query(ParsedChunkDB)
            .filter(ParsedChunkDB.doc_id == doc_id)
            .order_by(ParsedChunkDB.order)
            .all()
        )
        md_content = md_exporter.export_from_db_chunks(all_db_chunks, doc_id, doc.original_name)
        get_storage().save(f"markdowns/{doc_id}.md", md_content.encode("utf-8"))
        doc.markdown_path = f"markdowns/{doc_id}.md"
        db.commit()

        # ── MD → ChromaDB ─────────────────────────────────────────────────────
        vector_store.delete_doc(doc_id)
        index_chunks = md_chunker.chunk_from_text(md_content, doc_id)
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

    return DocumentMeta(
        id=doc.id,
        original_name=doc.original_name,
        file_size=doc.file_size,
        chunk_count=doc.chunk_count,
        status=doc.status,
        uploaded_at=doc.uploaded_at,
        indexed_at=doc.indexed_at,
        markdown_path=doc.markdown_path,
    )

@router.get("", response_model=list[DocumentMeta])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        DocumentMeta(
            id=d.id,
            original_name=d.original_name,
            file_size=d.file_size,
            chunk_count=d.chunk_count,
            status=d.status,
            uploaded_at=d.uploaded_at,
            indexed_at=d.indexed_at,
            markdown_path=d.markdown_path,
        )
        for d in docs
    ]

@router.post("/{doc_id}/reparse", response_model=DocumentMeta)
def reparse_document(
    doc_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """기존 ParsedChunkDB 청크를 삭제하고 PDF를 다시 파싱하여 저장한다."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage = get_storage()
    if not storage.exists(f"documents/{doc_id}.pdf"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF 파일이 없습니다")

    db.query(ParsedChunkDB).filter(ParsedChunkDB.doc_id == doc_id).delete()

    try:
        file_bytes = storage.load(f"documents/{doc_id}.pdf")
        parsed = pdf_parser.parse_pdf(file_bytes)
        parsed = noise_remover.remove_noise(parsed)

        for order, chunk in enumerate(parsed):
            bbox_json = None
            if chunk.bbox:
                x0, y0, x1, y1, pw, ph = chunk.bbox
                bbox_json = json.dumps({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "pw": pw, "ph": ph})
            db_chunk = ParsedChunkDB(
                id=chunk.id,
                doc_id=doc_id,
                type=chunk.type.value,
                content=chunk.content,
                page=chunk.page,
                section=chunk.section,
                order=order,
                is_heading=chunk.is_heading,
                heading_level=chunk.heading_level,
                image_b64=chunk.image_b64,
                bbox_json=bbox_json,
                status="pending",
                metadata_json=json.dumps(chunk.metadata),
            )
            db.add(db_chunk)

        doc.chunk_count = len(parsed)
        doc.status = "parsing"
        doc.indexed_at = None
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = "error"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"재파싱 중 오류: {str(e)}",
        ) from e

    return DocumentMeta(
        id=doc.id,
        original_name=doc.original_name,
        file_size=doc.file_size,
        chunk_count=doc.chunk_count,
        status=doc.status,
        uploaded_at=doc.uploaded_at,
        indexed_at=doc.indexed_at,
        markdown_path=doc.markdown_path,
    )

@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage = get_storage()
    vector_store.delete_doc(doc_id)
    db.query(ParsedChunkDB).filter(ParsedChunkDB.doc_id == doc_id).delete()
    storage.delete(f"documents/{doc_id}.pdf")
    storage.delete(f"markdowns/{doc_id}.md")
    db.delete(doc)
    db.commit()

@router.get("/{doc_id}/file", response_class=Response)
def get_pdf_file(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """원본 PDF 파일 반환 (pdfjs-dist 클라이언트 렌더링용)."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        pdf_bytes = get_storage().load(f"documents/{doc_id}.pdf")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{doc.original_name}"',
        },
    )

@router.get("/{doc_id}/page/{page_num}", response_class=Response)
def get_page_preview(
    doc_id: str,
    page_num: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PDF 특정 페이지를 PNG 이미지로 반환 (문서 미리보기용)."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        pdf_bytes = get_storage().load(f"documents/{doc_id}.pdf")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found")

    try:
        # stream= 방식: 파일 경로 불필요 (Supabase 등 원격 스토리지 호환)
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_idx = max(0, page_num - 1)
        if page_idx >= len(pdf):
            page_idx = len(pdf) - 1
        page = pdf[page_idx]
        mat = fitz.Matrix(1.5, 1.5)
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        pdf.close()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"페이지 렌더링 오류: {str(e)}",
        ) from e

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/{doc_id}/summarize", response_model=SummarizeResponse)
def summarize_document(
    doc_id: str,
    body: VlmRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """heading 청크 이후 본문을 LLM으로 요약 → SUMMARY 타입 청크 삽입."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db_chunks = (
        db.query(ParsedChunkDB)
        .filter(ParsedChunkDB.doc_id == doc_id, ParsedChunkDB.status != "discarded")
        .order_by(ParsedChunkDB.order)
        .all()
    )

    try:
        llm = LLMClient(provider=body.provider, api_token=body.api_token)
        inserted = summary_generator.generate_for_doc(db_chunks, llm, db, doc_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"요약 생성 중 오류: {str(e)}",
        ) from e
    return SummarizeResponse(inserted=inserted)

@router.post("/{doc_id}/noise/candidates", response_model=NoiseCandidatesResponse)
def get_noise_candidates(
    doc_id: str,
    custom_patterns: list[str] = Body(default=[]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """노이즈 후보 목록 반환 (삭제 없음)."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db_chunks = (
        db.query(ParsedChunkDB)
        .filter(ParsedChunkDB.doc_id == doc_id, ParsedChunkDB.type == "text")
        .all()
    )

    from app.modules.pdf_parser import ParsedChunk as PC
    parsed_chunks = [
        PC(
            id=c.id,
            type=ChunkType.TEXT,
            content=c.content,
            page=c.page,
            section=c.section,
            is_heading=c.is_heading,
            heading_level=c.heading_level,
        )
        for c in db_chunks
    ]

    candidates = find_candidates(parsed_chunks, custom_patterns or None)
    return NoiseCandidatesResponse(
        candidates=[
            NoiseCandidateItem(text=c.text, count=c.count, chunk_ids=c.chunk_ids)
            for c in candidates
        ]
    )

@router.get("/{doc_id}/markdown")
def get_markdown(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """저장된 MD 파일 내용 반환."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not doc.markdown_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MD 파일이 없습니다. 먼저 인덱싱을 실행하세요.",
        )

    try:
        content = get_storage().load(f"markdowns/{doc_id}.md").decode("utf-8")
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MD 파일이 스토리지에 없습니다.",
        )

    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="{doc_id}.md"'},
    )
