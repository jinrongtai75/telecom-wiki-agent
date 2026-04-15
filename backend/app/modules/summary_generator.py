"""
섹션 요약 생성 모듈 — preprocessing-master에서 포팅.
heading 청크 이후 본문을 LLM 한 문장으로 요약 → SUMMARY 타입 ParsedChunkDB 삽입.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.db_models import ParsedChunkDB
from app.modules.llm_client import LLMClient

SUMMARY_PROMPT = (
    "다음 섹션({heading})의 내용을 기술적으로 정확하게 한 문장으로 요약해주세요. "
    "불필요한 설명 없이 핵심 내용만 간결하게 작성하세요.\n\n"
    "{body}"
)


class SummaryGenerator:
    def generate_for_doc(
        self,
        chunks: list[ParsedChunkDB],
        llm: LLMClient,
        db: Session,
        doc_id: str,
    ) -> int:
        """
        1. 기존 summary 타입 청크 삭제
        2. heading 청크 순회 → 다음 heading 전까지 본문 수집
        3. LLM 요약 → SUMMARY ParsedChunkDB 삽입 (heading 바로 다음 order)
        4. 전체 order 재인덱싱
        반환: 삽입된 summary 청크 수
        """
        # 1. 기존 summary 청크 삭제
        db.query(ParsedChunkDB).filter(
            ParsedChunkDB.doc_id == doc_id,
            ParsedChunkDB.type == "summary",
        ).delete()
        db.flush()

        # discarded 제외, order 정렬
        active = (
            db.query(ParsedChunkDB)
            .filter(
                ParsedChunkDB.doc_id == doc_id,
                ParsedChunkDB.status != "discarded",
            )
            .order_by(ParsedChunkDB.order)
            .all()
        )

        # 2. heading 위치와 각 섹션 본문 수집
        sections: list[tuple[int, str, list[str]]] = []  # (heading_idx, heading_text, body_lines)
        current_heading_idx: int | None = None
        current_heading_text = ""
        current_body: list[str] = []

        for i, chunk in enumerate(active):
            if chunk.is_heading:
                if current_heading_idx is not None and current_body:
                    sections.append((current_heading_idx, current_heading_text, current_body))
                current_heading_idx = i
                current_heading_text = chunk.processed_content or chunk.content or ""
                current_body = []
            else:
                if current_heading_idx is not None:
                    effective = chunk.processed_content or chunk.content or ""
                    if effective.strip():
                        current_body.append(effective)

        # 마지막 섹션 처리
        if current_heading_idx is not None and current_body:
            sections.append((current_heading_idx, current_heading_text, current_body))

        if not sections:
            db.commit()
            return 0

        # 3. LLM 요약 생성 및 삽입
        inserted_count = 0
        # 역순으로 삽입하면 order 충돌 없이 처리 가능
        for heading_idx, heading_text, body_lines in reversed(sections):
            body_text = "\n\n".join(body_lines[:10])  # 최대 10개 본문 청크
            prompt = SUMMARY_PROMPT.format(
                heading=heading_text[:100],
                body=body_text[:2000],
            )
            try:
                summary_text = llm.complete(prompt, max_tokens=300).strip()
            except Exception:
                continue

            if not summary_text:
                continue

            # heading 바로 다음에 삽입될 order 값 (fractional 방식으로 임시 삽입)
            # 전체 재인덱싱 후 정렬됨
            insert_after_order = active[heading_idx].order

            summary_chunk = ParsedChunkDB(
                id=f"sum-{uuid.uuid4().hex[:8]}",
                doc_id=doc_id,
                type="summary",
                content=summary_text,
                processed_content=None,
                page=active[heading_idx].page,
                section=active[heading_idx].section,
                order=insert_after_order,  # 임시; 재인덱싱에서 조정
                is_heading=False,
                heading_level=0,
                status="confirmed",
                metadata_json="{}",
            )
            db.add(summary_chunk)
            inserted_count += 1

        db.flush()

        # 4. 전체 order 재인덱싱
        # heading 직후에 summary가 오도록: heading order 기준 sort + summary는 +0.5
        all_active = (
            db.query(ParsedChunkDB)
            .filter(
                ParsedChunkDB.doc_id == doc_id,
                ParsedChunkDB.status != "discarded",
            )
            .all()
        )

        # summary 청크를 이전 heading과 같은 order 값으로 넣었으므로
        # 정렬 시 같은 order면 summary가 heading 뒤에 오도록 type 기준 2차 정렬
        def sort_key(c: ParsedChunkDB) -> tuple:
            type_order = 0 if c.type != "summary" else 1
            return (c.order, type_order, c.id)

        all_active_sorted = sorted(all_active, key=sort_key)

        for new_order, chunk in enumerate(all_active_sorted):
            chunk.order = new_order

        db.commit()
        return inserted_count


summary_generator = SummaryGenerator()
