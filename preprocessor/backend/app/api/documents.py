import uuid
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import quote
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import Response
from pydantic import BaseModel

from app.models import (
    DocumentObject, ObjectType, ConfirmStatus, NoisePatterns,
    ProcessedDocument, ParseResult, BBox, NoiseCandidate,
)
from app.modules.parser import Parser
from app.modules.noise_remover import NoiseRemover
from app.modules.summary_generator import SummaryGenerator
from app.modules.md_exporter import MDExporter

router = APIRouter(prefix="/api/documents", tags=["documents"])

# 인메모리 저장소
_docs: dict[str, ProcessedDocument] = {}
_parse_results: dict[str, ParseResult] = {}
_raw_files: dict[str, tuple[bytes, str]] = {}  # doc_id -> (bytes, mime_type)

parser = Parser()
noise_remover = NoiseRemover()
summary_gen = SummaryGenerator()
md_exporter = MDExporter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_doc(doc_id: str) -> ProcessedDocument:
    doc = _docs.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    return doc


# ── 업로드 ────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "unknown"
    content = await file.read()
    try:
        result = parser.parse(content, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파싱 중 오류가 발생했습니다: {e}")

    _parse_results[result.document_id] = result
    _raw_files[result.document_id] = (content, file.content_type or "application/octet-stream")
    doc = ProcessedDocument(
        document_id=result.document_id,
        source_filename=filename,
        format=result.format,
        objects=result.objects,
        created_at=_now(),
        updated_at=_now(),
    )
    _docs[doc.document_id] = doc
    return {"document_id": doc.document_id, "format": doc.format, "objects": doc.objects, "raw_content": result.raw_content}



# ── 노이즈 제거 ───────────────────────────────────────────────────────────────

@router.get("/{doc_id}/denoise/candidates")
async def get_denoise_candidates(doc_id: str):
    doc = _get_doc(doc_id)
    candidates = noise_remover.find_candidates(doc.objects)
    return {"candidates": candidates}


class DenoiseRequest(BaseModel):
    delete_ids: Optional[List[str]] = None
    patterns: Optional[NoisePatterns] = None


@router.post("/{doc_id}/denoise")
async def denoise(doc_id: str, body: Optional[DenoiseRequest] = None):
    doc = _get_doc(doc_id)

    patterns = body.patterns if body else None
    delete_ids = set(body.delete_ids) if body and body.delete_ids else set()

    if patterns:
        all_patterns = patterns.header_patterns + patterns.footer_patterns + patterns.page_number_patterns
        invalid = noise_remover.validate_patterns(all_patterns)
        if invalid:
            raise HTTPException(status_code=400, detail=f"올바르지 않은 패턴입니다: {invalid}")

    # ID 직접 지정 제거
    if delete_ids:
        doc.objects = [o for o in doc.objects if o.id not in delete_ids]
        for i, o in enumerate(doc.objects):
            o.order = i

    # 패턴 기반 제거
    if patterns:
        doc.objects = noise_remover.remove_noise(doc.objects, patterns)

    doc.updated_at = _now()
    return {"objects": doc.objects}


# ── 소제목 요약 ───────────────────────────────────────────────────────────────

class SummarizeSelectionRequest(BaseModel):
    selected_ids: List[str]


@router.post("/{doc_id}/summarize-selection")
async def summarize_selection(doc_id: str, body: SummarizeSelectionRequest):
    doc = _get_doc(doc_id)
    if not body.selected_ids:
        raise HTTPException(status_code=400, detail="선택된 객체가 없습니다")
    try:
        doc.objects = summary_gen.generate_summary_for_selection(doc.objects, body.selected_ids)
        doc.updated_at = _now()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"objects": doc.objects}


# ── 수동 객체 지정 ────────────────────────────────────────────────────────────

class ManualObjectRequest(BaseModel):
    type: ObjectType
    content: str
    after_order: Optional[int] = None
    bbox: Optional[BBox] = None
    page: Optional[int] = None


class ReorderRequest(BaseModel):
    ordered_ids: List[str]


@router.post("/{doc_id}/objects/reorder")
async def reorder_objects(doc_id: str, body: ReorderRequest):
    doc = _get_doc(doc_id)
    id_to_obj = {o.id: o for o in doc.objects}
    reordered = [id_to_obj[oid] for oid in body.ordered_ids if oid in id_to_obj]
    # ordered_ids에 없는 객체는 뒤에 붙임
    rest = [o for o in doc.objects if o.id not in set(body.ordered_ids)]
    doc.objects = reordered + rest
    for i, o in enumerate(doc.objects):
        o.order = i
    doc.updated_at = _now()
    return {"objects": doc.objects}


@router.post("/{doc_id}/objects/manual")
async def add_manual_object(doc_id: str, body: ManualObjectRequest):
    doc = _get_doc(doc_id)

    content = body.content

    # 표 영역 지정 시: bbox 영역을 PyMuPDF로 파싱해 GFM 마크다운 생성
    if body.type == ObjectType.TABLE and not content and body.bbox is not None and body.page is not None:
        raw = _raw_files.get(doc_id)
        if raw and raw[1] == 'application/pdf':
            try:
                import fitz
                b = body.bbox
                pdf_doc = fitz.open(stream=raw[0], filetype='pdf')
                page = pdf_doc[body.page - 1]
                clip = fitz.Rect(b.x0, b.y0, b.x1, b.y1)
                # 지정 영역 안에서 표 파싱 시도
                found = False
                try:
                    for tab in page.find_tables(clip=clip).tables:
                        rows = tab.extract()
                        if rows:
                            md_rows = []
                            for i, row in enumerate(rows):
                                cells = [str(c or "").replace("\n", " ") for c in row]
                                md_rows.append("| " + " | ".join(cells) + " |")
                                if i == 0:
                                    md_rows.append("|" + "|".join(["---"] * len(cells)) + "|")
                            content = "\n".join(md_rows)
                            found = True
                            break
                except Exception:
                    pass
                # find_tables 실패 시 영역 텍스트를 그대로 추출
                if not found:
                    content = page.get_text("text", clip=clip).strip()
                pdf_doc.close()
            except Exception:
                pass

    new_obj = DocumentObject(
        id=f"obj-{uuid.uuid4().hex[:8]}",
        type=body.type,
        content=content,
        order=len(doc.objects),
        bbox=body.bbox,
        page=body.page,
    )

    # 이미지 영역 지정 시: bbox 안에 있는 text 객체 제거
    if body.type == ObjectType.IMAGE and body.bbox is not None and body.page is not None:
        b = body.bbox
        def _overlaps(obj: DocumentObject) -> bool:
            if obj.type != ObjectType.TEXT or obj.page != body.page or obj.bbox is None:
                return False
            ob = obj.bbox
            cx = (ob.x0 + ob.x1) / 2
            cy = (ob.y0 + ob.y1) / 2
            return b.x0 <= cx <= b.x1 and b.y0 <= cy <= b.y1
        doc.objects = [o for o in doc.objects if not _overlaps(o)]

    if body.after_order is not None:
        insert_at = body.after_order + 1
        doc.objects.insert(insert_at, new_obj)
    else:
        doc.objects.append(new_obj)

    for i, obj in enumerate(doc.objects):
        obj.order = i

    doc.updated_at = _now()
    return {"object": new_obj, "objects": doc.objects}


# ── JSON 내보내기 / 로드 ───────────────────────────────────────────────────────

@router.get("/{doc_id}/export")
async def export_document(
    doc_id: str,
    force: bool = False,
    save_path: Optional[str] = None,
    filename: Optional[str] = None,
):
    from pathlib import Path

    doc = _get_doc(doc_id)

    if not force:
        unconfirmed = md_exporter.validate_all_confirmed(doc)
        if unconfirmed:
            raise HTTPException(
                status_code=400,
                detail=f"확인되지 않은 객체가 있습니다. 모든 객체를 확인한 후 내보내기를 진행해주세요. 미확인 객체: {unconfirmed}",
            )

    md_content = md_exporter.export(doc)
    default_filename = doc.source_filename.rsplit(".", 1)[0] + ".md"
    out_filename = filename if filename else default_filename
    if not out_filename.endswith(".md"):
        out_filename += ".md"

    # 서버 경로 저장
    if save_path:
        try:
            out_dir = Path(save_path)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / out_filename).write_text(md_content, encoding="utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"파일 저장 실패: {e}")

    return Response(
        content=md_content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(out_filename)}"},
    )



@router.get("/{doc_id}/file")
async def get_raw_file(doc_id: str):
    """업로드된 원본 파일(PDF 등)을 그대로 반환 — PDF.js 렌더링용"""
    entry = _raw_files.get(doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="원본 파일을 찾을 수 없습니다")
    file_bytes, mime = entry
    return Response(content=file_bytes, media_type=mime)
