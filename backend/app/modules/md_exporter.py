"""
MD 내보내기 모듈 — preprocessing-master에서 포팅.
ParsedChunkDB 목록 → Markdown 파일 직렬화.
HTML 주석으로 메타데이터 보존 (round-trip 지원).
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.models.db_models import ParsedChunkDB


class MDExporter:
    def export_from_db_chunks(
        self,
        chunks: list[ParsedChunkDB],
        doc_id: str,
        source_name: str,
    ) -> str:
        """
        ParsedChunkDB 목록을 Markdown 문자열로 변환.
        discarded 청크는 제외, order 기준으로 정렬.
        """
        active = sorted(
            [c for c in chunks if c.status != "discarded"],
            key=lambda x: x.order,
        )
        now = datetime.now(UTC).isoformat()
        lines: list[str] = [
            f"<!-- doc:{doc_id} source:{source_name} created_at:{now} -->",
            "",
        ]

        for chunk in active:
            effective = chunk.processed_content or chunk.content or ""

            # 객체 메타 주석 (round-trip 복원용)
            lines.append(
                f"<!-- obj:{chunk.id} type:{chunk.type} page:{chunk.page}"
                f" status:{chunk.status} -->"
            )

            if chunk.type == "summary":
                lines.append(f"> **요약**: {effective}")

            elif chunk.is_heading:
                level = max(1, chunk.heading_level or 1)
                lines.append(f"{'#' * level} {effective}")

            elif chunk.type == "table":
                lines.append(effective)

            elif chunk.type == "image":
                if chunk.image_path:
                    lines.append(f"![image]({chunk.image_path})")
                # VLM 처리된 설명 또는 원본 alt text
                if effective:
                    lines.append(effective)

            else:
                # 일반 텍스트 본문
                lines.append(effective)

            lines.append("")  # 청크 사이 빈 줄

        return "\n".join(lines)

    def save(self, content: str, path: str) -> None:
        """Markdown 내용을 파일로 저장. 상위 디렉터리가 없으면 생성."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def load(self, path: str) -> str:
        """저장된 MD 파일 내용을 반환."""
        return Path(path).read_text(encoding="utf-8")


md_exporter = MDExporter()
