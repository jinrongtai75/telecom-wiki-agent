import uuid
from typing import List

from app.models import DocumentObject, ObjectType, ConfirmStatus
from app.modules.llm_client import call_llm


def _new_id() -> str:
    return f"obj-{uuid.uuid4().hex[:8]}"


class SummaryGenerator:
    def identify_headings(self, objects: List[DocumentObject]) -> List[int]:
        return [i for i, obj in enumerate(objects) if obj.is_heading]

    def generate_summaries(
        self, objects: List[DocumentObject], heading_indices: List[int]
    ) -> List[DocumentObject]:
        result = list(objects)
        for idx in sorted(heading_indices, reverse=True):
            heading_obj = result[idx]
            body_texts = []
            for j in range(idx + 1, len(result)):
                if result[j].is_heading:
                    break
                if result[j].type == ObjectType.TEXT:
                    body_texts.append(result[j].content)

            body = "\n".join(body_texts)
            summary_text = call_llm(
                f"다음 섹션({heading_obj.content})의 내용을 한 문장으로 요약해주세요:\n\n{body}",
                max_tokens=300,
            )
            summary_obj = DocumentObject(
                id=_new_id(),
                type=ObjectType.SUMMARY,
                content=summary_text,
                order=heading_obj.order + 1,
                page=heading_obj.page,
                metadata={},
                confirm_status=ConfirmStatus.CONFIRMED,
            )
            result.insert(idx + 1, summary_obj)

        for i, obj in enumerate(result):
            obj.order = i
        return result

    def generate_summary_for_selection(
        self, objects: List[DocumentObject], selected_ids: List[str]
    ) -> List[DocumentObject]:
        id_set = set(selected_ids)
        selected = [o for o in objects if o.id in id_set]
        if not selected:
            raise ValueError("선택된 객체를 찾을 수 없습니다")

        selected_sorted = sorted(selected, key=lambda o: o.order)
        body = "\n\n".join(obj.processed_content or obj.content for obj in selected_sorted)

        summary_text = call_llm(
            f"다음 내용을 한 문단으로 요약해주세요:\n\n{body}",
            max_tokens=300,
        )

        summary_obj = DocumentObject(
            id=_new_id(),
            type=ObjectType.SUMMARY,
            content=summary_text,
            order=0,
            page=selected_sorted[0].page,
            metadata={},
            confirm_status=ConfirmStatus.CONFIRMED,
        )

        first_order = selected_sorted[0].order
        result = list(objects)
        insert_at = next((i for i, o in enumerate(result) if o.order == first_order), 0)
        result.insert(insert_at, summary_obj)

        for i, o in enumerate(result):
            o.order = i
        return result

    def set_heading(self, obj: DocumentObject, is_heading: bool) -> DocumentObject:
        obj.is_heading = is_heading
        return obj
