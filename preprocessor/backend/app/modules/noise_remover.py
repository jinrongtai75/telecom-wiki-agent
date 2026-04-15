import re
from typing import List, Optional
from app.models import DocumentObject, NoisePatterns, NoiseCandidate


DEFAULT_PAGE_PATTERNS = [r"^\d+$", r"^- \d+ -$", r"^- \d+ —$", r"^\d+ / \d+$"]


class NoiseRemover:
    def remove_noise(
        self,
        objects: List[DocumentObject],
        custom_patterns: Optional[NoisePatterns] = None,
    ) -> List[DocumentObject]:
        header_res = self._compile(custom_patterns.header_patterns if custom_patterns else [])
        footer_res = self._compile(custom_patterns.footer_patterns if custom_patterns else [])
        page_res = self._compile(
            (custom_patterns.page_number_patterns if custom_patterns else []) + DEFAULT_PAGE_PATTERNS
        )
        contains_list = custom_patterns.contains_patterns if custom_patterns else []

        # 반복 헤더/푸터 감지 — 3회 이상 등장하는 짧은 텍스트
        text_counts: dict[str, int] = {}
        for obj in objects:
            if obj.type.value == "text":
                t = obj.content.strip()
                if len(t) <= 200:
                    text_counts[t] = text_counts.get(t, 0) + 1
        repeated = {t for t, c in text_counts.items() if c >= 3}

        result = []
        for obj in objects:
            if obj.type.value != "text":
                result.append(obj)
                continue
            content = obj.content.strip()
            if self._matches_any(content, page_res):
                continue
            if self._matches_any(content, header_res):
                continue
            if self._matches_any(content, footer_res):
                continue
            if content in repeated:
                continue
            if any(p in content for p in contains_list if p):
                continue
            result.append(obj)

        # order 재정렬
        for i, obj in enumerate(result):
            obj.order = i
        return result

    def find_candidates(self, objects: List[DocumentObject]) -> List[NoiseCandidate]:
        """노이즈 후보 탐지 — 문서를 수정하지 않고 후보 목록만 반환"""
        page_res = self._compile(DEFAULT_PAGE_PATTERNS)

        # 반복 텍스트 집계
        text_to_ids: dict[str, List[str]] = {}
        for obj in objects:
            if obj.type.value != "text":
                continue
            t = obj.content.strip()
            if len(t) <= 200:
                text_to_ids.setdefault(t, []).append(obj.id)

        candidates: List[NoiseCandidate] = []
        seen: set[str] = set()

        for obj in objects:
            if obj.type.value != "text":
                continue
            t = obj.content.strip()
            if t in seen:
                continue
            ids = text_to_ids.get(t, [obj.id])
            # 반복 텍스트 (3회 이상)
            if len(ids) >= 3:
                seen.add(t)
                candidates.append(NoiseCandidate(text=t, count=len(ids), object_ids=ids))
            # 페이지 번호 패턴
            elif self._matches_any(t, page_res):
                seen.add(t)
                candidates.append(NoiseCandidate(text=t, count=len(ids), object_ids=ids))

        return candidates

    def _compile(self, patterns: List[str]) -> List[re.Pattern]:
        compiled = []
        for p in patterns:
            try:
                compiled.append(re.compile(p))
            except re.error:
                pass  # 잘못된 패턴은 건너뜀
        return compiled

    def validate_patterns(self, patterns: List[str]) -> List[str]:
        invalid = []
        for p in patterns:
            try:
                re.compile(p)
            except re.error:
                invalid.append(p)
        return invalid

    def _matches_any(self, text: str, patterns: List[re.Pattern]) -> bool:
        return any(p.search(text) for p in patterns)
