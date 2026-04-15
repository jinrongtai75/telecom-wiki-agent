from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.models import ConfirmStatus
from app.modules.table_processor import TableProcessor
from app.modules.image_processor import ImageProcessor
from app.api.documents import _docs, _raw_files

router = APIRouter(prefix='/api/objects', tags=['objects'])
table_proc = TableProcessor()
image_proc = ImageProcessor()


def _get_obj(doc_id: str, obj_id: str):
    doc = _docs.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail='문서를 찾을 수 없습니다')
    for obj in doc.objects:
        if obj.id == obj_id:
            return doc, obj
    raise HTTPException(status_code=404, detail='객체를 찾을 수 없습니다')


class ChatRequest(BaseModel):
    message: str


class ImageLinkRequest(BaseModel):
    target_text: str
    save_dir: Optional[str] = ''


class UpdateContentRequest(BaseModel):
    processed_content: Optional[str] = None
    is_heading: Optional[bool] = None


class HeadingRequest(BaseModel):
    is_heading: bool


class UpdateContentRequest2(BaseModel):
    content: Optional[str] = None
    processed_content: Optional[str] = None

@router.post('/{doc_id}/{obj_id}/table/process')
async def process_table(doc_id: str, obj_id: str):
    doc, obj = _get_obj(doc_id, obj_id)
    if obj.type.value != 'table':
        raise HTTPException(status_code=400, detail='테이블 객체가 아닙니다')
    result = table_proc.to_dataframe(obj)
    obj.processed_content = result
    return {'processed_content': result}


@router.post('/{doc_id}/{obj_id}/table/flatten')
async def flatten_table(doc_id: str, obj_id: str):
    doc, obj = _get_obj(doc_id, obj_id)
    if obj.type.value != 'table':
        raise HTTPException(status_code=400, detail='테이블 객체가 아닙니다')
    try:
        raw = _raw_files.get(doc_id)
        if raw and raw[1] == 'application/pdf' and obj.bbox and obj.page:
            import fitz, base64
            pdf_doc = fitz.open(stream=raw[0], filetype='pdf')
            page = pdf_doc[obj.page - 1]
            clip = fitz.Rect(obj.bbox.x0, obj.bbox.y0, obj.bbox.x1, obj.bbox.y1)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip)
            img_bytes = pix.tobytes('png')
            pdf_doc.close()
            b64 = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"
            result = table_proc.flatten_with_vlm(b64)
        else:
            result = table_proc.flatten_with_llm(obj)
        obj.processed_content = result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {'processed_content': result}


@router.post('/{doc_id}/{obj_id}/table/review')
async def review_table(doc_id: str, obj_id: str):
    doc, obj = _get_obj(doc_id, obj_id)
    if obj.type.value != 'table':
        raise HTTPException(status_code=400, detail='테이블 객체가 아닙니다')
    try:
        parsed = obj.processed_content or obj.content
        raw = _raw_files.get(doc_id)
        if raw and raw[1] == 'application/pdf' and obj.bbox and obj.page:
            import fitz, base64
            pdf_doc = fitz.open(stream=raw[0], filetype='pdf')
            page = pdf_doc[obj.page - 1]
            clip = fitz.Rect(obj.bbox.x0, obj.bbox.y0, obj.bbox.x1, obj.bbox.y1)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip)
            img_bytes = pix.tobytes('png')
            pdf_doc.close()
            b64 = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"
            decision = table_proc.review_with_vlm(b64, parsed)
        else:
            decision = table_proc.review_with_llm(parsed)
        action = decision.get("action", "keep")
        if action == "flatten":
            obj.processed_content = decision.get("result", parsed)
        return {"action": action, "processed_content": obj.processed_content}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post('/{doc_id}/{obj_id}/table/chat')
async def chat_table(doc_id: str, obj_id: str, body: ChatRequest):
    doc, obj = _get_obj(doc_id, obj_id)
    current = obj.processed_content or obj.content
    try:
        result = table_proc.chat_edit(current, body.message)
        obj.processed_content = result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {'processed_content': result}


def _ensure_image_content(doc_id: str, obj) -> None:
    if not obj.content and obj.bbox and obj.page:
        raw = _raw_files.get(doc_id)
        if not raw:
            raise ValueError('원본 PDF 파일을 찾을 수 없습니다')
        import fitz, base64
        pdf_doc = fitz.open(stream=raw[0], filetype='pdf')
        page = pdf_doc[obj.page - 1]
        clip = fitz.Rect(obj.bbox.x0, obj.bbox.y0, obj.bbox.x1, obj.bbox.y1)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip)
        img_bytes = pix.tobytes('png')
        pdf_doc.close()
        b64 = base64.b64encode(img_bytes).decode()
        obj.content = f'data:image/png;base64,{b64}'


@router.post('/{doc_id}/{obj_id}/image/link')
async def link_image(doc_id: str, obj_id: str, body: ImageLinkRequest):
    doc, obj = _get_obj(doc_id, obj_id)
    if obj.type.value != 'image':
        raise HTTPException(status_code=400, detail='이미지 객체가 아닙니다')
    try:
        _ensure_image_content(doc_id, obj)
        updated = image_proc.save_and_link(obj, body.target_text, body.save_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'image_path': updated.image_path, 'processed_content': updated.processed_content}


@router.post('/{doc_id}/{obj_id}/image/interpret')
async def interpret_image(doc_id: str, obj_id: str):
    doc, obj = _get_obj(doc_id, obj_id)
    if obj.type.value != 'image':
        raise HTTPException(status_code=400, detail='이미지 객체가 아닙니다')
    try:
        _ensure_image_content(doc_id, obj)
        updated = image_proc.interpret_with_vlm(obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {'processed_content': updated.processed_content, 'image_path': updated.image_path}


@router.post('/{doc_id}/{obj_id}/image/review')
async def review_image(doc_id: str, obj_id: str):
    doc, obj = _get_obj(doc_id, obj_id)
    if obj.type.value != 'image':
        raise HTTPException(status_code=400, detail='이미지 객체가 아닙니다')
    try:
        _ensure_image_content(doc_id, obj)
        decision = image_proc.review_with_vlm(obj.content)
        action = decision.get("action", "save")
        if action == "discard":
            doc.objects = [o for o in doc.objects if o.id != obj_id]
            for i, o in enumerate(doc.objects):
                o.order = i
            return {"action": "discard", "objects": doc.objects}
        elif action == "save":
            description = decision.get("description", "이미지")
            # save 시 항상 bbox 크롭 이미지를 사용 — embedded xref보다 정확함
            raw = _raw_files.get(doc_id)
            if raw and raw[1] == 'application/pdf' and obj.bbox and obj.page:
                import fitz, base64 as _b64
                pdf_doc = fitz.open(stream=raw[0], filetype='pdf')
                page = pdf_doc[obj.page - 1]
                clip = fitz.Rect(obj.bbox.x0, obj.bbox.y0, obj.bbox.x1, obj.bbox.y1)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip)
                img_bytes = pix.tobytes('png')
                pdf_doc.close()
                obj.content = f'data:image/png;base64,{_b64.b64encode(img_bytes).decode()}'
            updated = image_proc.save_and_link(obj, description)
            return {"action": "save", "processed_content": updated.processed_content, "image_path": updated.image_path}
        else:
            result = decision.get("result", "")
            obj.processed_content = result
            return {"action": "describe", "processed_content": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post('/{doc_id}/{obj_id}/image/chat')
async def chat_image(doc_id: str, obj_id: str, body: ChatRequest):
    doc, obj = _get_obj(doc_id, obj_id)
    current = obj.processed_content or ''
    try:
        result = image_proc.chat_edit(current, body.message)
        obj.processed_content = result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {'processed_content': result}


@router.post('/{doc_id}/{obj_id}/confirm')
async def confirm_object(doc_id: str, obj_id: str, body: Optional[UpdateContentRequest] = None):
    doc, obj = _get_obj(doc_id, obj_id)
    if body and body.processed_content is not None:
        obj.processed_content = body.processed_content
    if body and body.is_heading is not None:
        obj.is_heading = body.is_heading
    obj.confirm_status = ConfirmStatus.CONFIRMED
    return {'id': obj.id, 'confirm_status': obj.confirm_status, 'processed_content': obj.processed_content}


@router.patch('/{doc_id}/{obj_id}/content')
async def update_content(doc_id: str, obj_id: str, body: UpdateContentRequest2):
    doc, obj = _get_obj(doc_id, obj_id)
    if body.content is not None:
        obj.content = body.content
    if body.processed_content is not None:
        obj.processed_content = body.processed_content
    return {'id': obj.id, 'content': obj.content, 'processed_content': obj.processed_content}


@router.post('/{doc_id}/{obj_id}/heading')
async def set_heading(doc_id: str, obj_id: str, body: HeadingRequest):
    doc, obj = _get_obj(doc_id, obj_id)
    obj.is_heading = body.is_heading
    return {'id': obj.id, 'is_heading': obj.is_heading}


@router.delete('/{doc_id}/{obj_id}')
async def delete_object(doc_id: str, obj_id: str):
    doc, obj = _get_obj(doc_id, obj_id)
    doc.objects = [o for o in doc.objects if o.id != obj_id]
    for i, o in enumerate(doc.objects):
        o.order = i
    return {'objects': doc.objects}
