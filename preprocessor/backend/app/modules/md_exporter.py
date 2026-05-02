import re
from datetime import datetime, timezone
from typing import List, Optional
from app.models import DocumentObject, DocumentFormat, ObjectType, ConfirmStatus, ProcessedDocument, NoisePatterns


class MDExporter:
    def export(self, document: ProcessedDocument) -> str:
        lines = []

        for obj in sorted(document.objects, key=lambda o: o.order):
            # wiki agent md_chunker가 파싱할 수 있는 메타데이터 주석 삽입
            meta_parts = [
                f"obj:{obj.id}",
                f"type:{obj.type.value}",
                f"order:{obj.order}",
                f"confirm:{obj.confirm_status.value}",
                f"page:{obj.page or 1}",
            ]
            if obj.image_path:
                meta_parts.append(f"image_path:{obj.image_path}")
            if obj.is_heading:
                meta_parts.append("is_heading:true")
            lines.append(f"<!-- {' '.join(meta_parts)} -->")

            rendered = self._render_object(obj)
            lines.append(rendered)
            lines.append("")

        return "\n".join(lines)

    def load(self, md_str: str) -> ProcessedDocument:
        doc_meta = self._parse_doc_meta(md_str)
        objects = self._parse_objects(md_str)
        return ProcessedDocument(
            document_id=doc_meta.get("doc", "unknown"),
            source_filename=doc_meta.get("source", "unknown"),
            format=DocumentFormat(doc_meta.get("format", "pdf")),
            objects=objects,
            created_at=doc_meta.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=doc_meta.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )

    def validate_all_confirmed(self, document: ProcessedDocument) -> List[str]:
        unconfirmed = []
        for obj in document.objects:
            if obj.type in (ObjectType.TABLE, ObjectType.IMAGE):
                if obj.confirm_status == ConfirmStatus.PENDING:
                    unconfirmed.append(obj.id)
        return unconfirmed

    # ── 렌더링 ──────────────────────────────────────────────────────────────
    def _render_object(self, obj: DocumentObject) -> str:
        content = obj.processed_content if obj.processed_content else obj.content

        if obj.type == ObjectType.SUMMARY:
            return f"> **요약**: {content}"

        if obj.type == ObjectType.TEXT:
            if obj.is_heading:
                # 메타데이터에서 heading level 추출
                tag = obj.metadata.get("tag", "")
                level = int(tag[1]) if tag and tag.startswith("h") and tag[1:].isdigit() else 2
                return f"{'#' * level} {content}"
            return content

        if obj.type == ObjectType.TABLE:
            return content  # 이미 GFM 형식

        if obj.type == ObjectType.IMAGE:
            alt = obj.metadata.get("alt") or obj.id
            if obj.image_path:
                # 링크 연결 모드: processed_content가 "텍스트 <경로>" 형식 → 설명 텍스트 추출
                if content and content.endswith(f" <{obj.image_path}>"):
                    description = content[: -(len(obj.image_path) + 3)].strip()
                else:
                    description = content
                return f"{description}\n<!-- image: {obj.image_path} -->"
            if content.startswith("data:image"):
                # base64를 MD에 직접 삽입하면 응답이 수 MB로 불어남 → 플레이스홀더로 대체
                return f"[이미지: {alt}]"
            if content.startswith("http"):
                return f"![{alt}]({content})"
            return content

        return content

    # ── 역직렬화 ────────────────────────────────────────────────────────────
    def _parse_doc_meta(self, md_str: str) -> dict:
        pattern = r"<!-- doc:(\S+) source:(\S+) format:(\S+) created_at:(\S+) updated_at:(\S+) -->"
        m = re.search(pattern, md_str)
        if not m:
            return {}
        return {
            "doc": m.group(1),
            "source": m.group(2),
            "format": m.group(3),
            "created_at": m.group(4),
            "updated_at": m.group(5),
        }

    def _parse_objects(self, md_str: str) -> List[DocumentObject]:
        obj_pattern = re.compile(
            r"<!-- obj:(\S+) type:(\S+) order:(\d+)"
            r"(?: confirm:(\S+))?"
            r"(?: page:(\d+))?"
            r"(?: image_path:(\S+))?"
            r"(?: is_heading:(true))?"
            r" -->\n([\s\S]*?)(?=\n<!-- (?:obj|doc):|\Z)"
        )
        objects = []
        for m in obj_pattern.finditer(md_str):
            obj_id = m.group(1)
            obj_type = ObjectType(m.group(2))
            order = int(m.group(3))
            confirm = ConfirmStatus(m.group(4)) if m.group(4) else ConfirmStatus.PENDING
            page = int(m.group(5)) if m.group(5) else None
            image_path = m.group(6) if m.group(6) else None
            is_heading = m.group(7) == "true"
            raw_content = m.group(8).strip()

            # 렌더링된 마크다운에서 원본 content 복원
            content = self._derender(raw_content, obj_type, is_heading, image_path)

            objects.append(
                DocumentObject(
                    id=obj_id,
                    type=obj_type,
                    content=content,
                    order=order,
                    page=page,
                    metadata={},
                    is_heading=is_heading,
                    confirm_status=confirm,
                    image_path=image_path,
                    processed_content=raw_content if raw_content != content else None,
                )
            )
        return objects

    def _derender(self, rendered: str, obj_type: ObjectType, is_heading: bool, image_path: Optional[str]) -> str:
        if obj_type == ObjectType.SUMMARY:
            return re.sub(r"^> \*\*요약\*\*: ", "", rendered)
        if obj_type == ObjectType.TEXT and is_heading:
            return re.sub(r"^#+\s*", "", rendered)
        if obj_type == ObjectType.IMAGE and image_path:
            m = re.match(r"!\[.*?\]\((.*?)\)", rendered)
            return m.group(1) if m else rendered
        return rendered
