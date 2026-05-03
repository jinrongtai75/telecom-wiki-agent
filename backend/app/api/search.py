import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.db_models import AppSetting, ChatHistory, Document, User
from app.models.schemas import SearchRequest, SearchResponse, SourceInfo
from app.modules import answer_gen, vector_store
from app.modules.llm_client import LLMClient
from app.modules.threegpp import search_3gpp
from app.security.auth_deps import get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])


def _resolve_token(api_token: str, db: Session) -> str:
    """api_token이 비어 있으면 DB에 저장된 gemini 키를 폴백으로 사용."""
    if api_token:
        return api_token
    setting = db.get(AppSetting, "gemini_token")
    if setting and setting.value:
        return setting.value
    return api_token


@router.post("", response_model=SearchResponse)
def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    llm = LLMClient(api_token=_resolve_token(req.api_token, db))

    # 1. 키워드 추출 (3GPP 폴백 전용)
    try:
        keywords = answer_gen.extract_keywords(req.question, llm)
    except Exception:
        keywords = req.question.split()[:5]

    # 2. ChromaDB 의미 검색 — 원문 질문으로 검색 (한국어 임베딩 일치)
    chunks = vector_store.search(req.question, top_k=settings.search_top_k)

    # 3. 관련성 판단
    relevant_chunks = [c for c in chunks if c["score"] >= settings.relevance_threshold]
    from_3gpp = False
    threegpp_results = None

    # 4. 관련 문서 없으면 3GPP 폴백
    if not relevant_chunks and settings.threegpp_enabled:
        threegpp_results = search_3gpp(keywords)
        from_3gpp = True

    use_chunks = relevant_chunks or chunks[:3]  # 임계값 미달이어도 상위 3개 활용

    # 5. LLM 답변 생성
    try:
        answer_text = answer_gen.generate_answer(
            req.question,
            use_chunks,
            llm,
            threegpp_results,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM 서비스 오류: {str(e)}",
        ) from e

    # 6. 출처 구성
    sources: list[SourceInfo] = []
    seen_docs: set[str] = set()

    for chunk in use_chunks:
        doc_id = chunk.get("doc_id", "")
        if doc_id in seen_docs:
            continue
        seen_docs.add(doc_id)

        # 문서명 조회
        doc = db.query(Document).filter(Document.id == doc_id).first()
        filename = doc.original_name if doc else doc_id

        sources.append(SourceInfo(
            doc_id=doc_id,
            filename=filename,
            page=chunk.get("page", 0),
            section=chunk.get("section", ""),
            score=chunk.get("score", 0.0),
            image_path=chunk.get("image_path"),
            from_3gpp=False,
        ))

    if threegpp_results:
        for r in threegpp_results[:3]:
            sources.append(SourceInfo(
                doc_id=r.spec_number,
                filename=r.title,
                page=0,
                section=r.url,
                score=0.5,
                from_3gpp=True,
            ))

    # 7. 히스토리 저장
    top_score = max((c["score"] for c in use_chunks), default=0.0)
    history = ChatHistory(
        user_id=current_user.id,
        question=req.question,
        answer=answer_text,
        sources=json.dumps([s.model_dump() for s in sources]),
        provider="gemini",
        relevance_score=top_score,
        from_3gpp=from_3gpp,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    return SearchResponse(
        answer=answer_text,
        sources=sources,
        provider="gemini",
        history_id=history.id,
    )


@router.post("/stream")
def search_stream(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    SSE 스트리밍 검색.
    이벤트 형식:
      data: {"type":"sources","data":[...]}   ← 먼저 출처 전송
      data: {"type":"token","data":"..."}     ← 답변 토큰 스트리밍
      data: {"type":"done","data":{"history_id":"..."}}
      data: {"type":"error","data":"..."}
    """
    llm = LLMClient(api_token=_resolve_token(req.api_token, db))

    def event_stream():
        # 1. 키워드 추출 (3GPP 폴백 전용) + ChromaDB 검색
        try:
            keywords = answer_gen.extract_keywords(req.question, llm)
        except Exception:
            keywords = req.question.split()[:5]

        chunks = vector_store.search(req.question, top_k=settings.search_top_k)
        relevant_chunks = [c for c in chunks if c["score"] >= settings.relevance_threshold]
        from_3gpp = False
        threegpp_results = None

        if not relevant_chunks and settings.threegpp_enabled:
            threegpp_results = search_3gpp(keywords)
            from_3gpp = True

        use_chunks = relevant_chunks or chunks[:3]

        # 2. 출처 먼저 전송
        sources: list[SourceInfo] = []
        seen_docs: set[str] = set()
        for chunk in use_chunks:
            doc_id = chunk.get("doc_id", "")
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            doc = db.query(Document).filter(Document.id == doc_id).first()
            filename = doc.original_name if doc else doc_id
            sources.append(SourceInfo(
                doc_id=doc_id,
                filename=filename,
                page=chunk.get("page", 0),
                section=chunk.get("section", ""),
                score=chunk.get("score", 0.0),
                image_path=chunk.get("image_path"),
                from_3gpp=False,
            ))
        if threegpp_results:
            for r in threegpp_results[:3]:
                sources.append(SourceInfo(
                    doc_id=r.spec_number,
                    filename=r.title,
                    page=0,
                    section=r.url,
                    score=0.5,
                    from_3gpp=True,
                ))

        yield f"data: {json.dumps({'type':'sources','data':[s.model_dump() for s in sources]}, ensure_ascii=False)}\n\n"

        # 3. 답변 스트리밍
        full_answer = ""
        try:
            if use_chunks:
                prompt = answer_gen._build_rag_prompt(req.question, use_chunks)
            elif threegpp_results:
                prompt = answer_gen._build_3gpp_prompt(req.question, threegpp_results)
            else:
                prompt = answer_gen._build_fallback_prompt(req.question)

            for token in llm.complete_stream(prompt, system=answer_gen.SYSTEM_PROMPT):
                full_answer += token
                yield f"data: {json.dumps({'type':'token','data':token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','data':str(e)}, ensure_ascii=False)}\n\n"
            return

        # 4. 히스토리 저장 후 done 이벤트
        top_score = max((c["score"] for c in use_chunks), default=0.0)
        history = ChatHistory(
            user_id=current_user.id,
            question=req.question,
            answer=full_answer,
            sources=json.dumps([s.model_dump() for s in sources]),
            provider="gemini",
            relevance_score=top_score,
            from_3gpp=from_3gpp,
        )
        db.add(history)
        db.commit()
        db.refresh(history)

        yield f"data: {json.dumps({'type':'done','data':{'history_id':history.id}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
