"""
노이즈 제거 모듈 — preprocessing-master에서 포팅.
헤더/푸터/페이지번호/반복 텍스트 제거.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.modules.pdf_parser import ChunkType, ParsedChunk

DEFAULT_PAGE_PATTERNS = [r"^\d+$", r"^- \d+ -$", r"^- \d+ —$", r"^\d+ / \d+$"]


@dataclass
class NoiseCandidateResult:
    text: str
    count: int
    chunk_ids: list[str] = field(default_factory=list)


def find_candidates(
    chunks: list[ParsedChunk],
    custom_patterns: list[str] | None = None,
) -> list[NoiseCandidateResult]:
    """
    노이즈 후보를 탐지하되 실제 삭제는 하지 않는다.
    사용자가 확인한 후 remove_noise()를 호출하도록 설계.
    """
    all_patterns = list(DEFAULT_PAGE_PATTERNS)
    if custom_patterns:
        for p in custom_patterns:
            try:
                re.compile(p)
                all_patterns.append(p)
            except re.error:
                pass

    page_res = _compile(all_patterns)

    # 반복 텍스트 탐지
    text_to_ids: dict[str, list[str]] = {}
    for chunk in chunks:
        if chunk.type == ChunkType.TEXT:
            t = chunk.content.strip()
            if len(t) <= 200:
                text_to_ids.setdefault(t, []).append(chunk.id)

    results: list[NoiseCandidateResult] = []
    seen: set[str] = set()

    for chunk in chunks:
        if chunk.type != ChunkType.TEXT:
            continue
        content = chunk.content.strip()
        if content in seen:
            continue

        if _matches_any(content, page_res):
            ids = text_to_ids.get(content, [chunk.id])
            results.append(NoiseCandidateResult(text=content, count=len(ids), chunk_ids=ids))
            seen.add(content)
        elif content in text_to_ids and len(text_to_ids[content]) >= 3:
            ids = text_to_ids[content]
            results.append(NoiseCandidateResult(text=content, count=len(ids), chunk_ids=ids))
            seen.add(content)

    # count 내림차순 정렬
    results.sort(key=lambda r: r.count, reverse=True)
    return results


def remove_noise(chunks: list[ParsedChunk]) -> list[ParsedChunk]:
    """
    텍스트 청크에서 헤더/푸터/페이지번호/반복 텍스트를 제거.
    표·이미지 청크는 그대로 통과.
    """
    page_res = _compile(DEFAULT_PAGE_PATTERNS)

    # 반복 텍스트 감지 (3회 이상 등장하는 짧은 텍스트)
    text_counts: dict[str, int] = {}
    for chunk in chunks:
        if chunk.type == ChunkType.TEXT:
            t = chunk.content.strip()
            if len(t) <= 200:
                text_counts[t] = text_counts.get(t, 0) + 1
    repeated = {t for t, c in text_counts.items() if c >= 3}

    result: list[ParsedChunk] = []
    for chunk in chunks:
        if chunk.type != ChunkType.TEXT:
            result.append(chunk)
            continue
        content = chunk.content.strip()
        if _matches_any(content, page_res):
            continue
        if content in repeated:
            continue
        result.append(chunk)

    return result


def _compile(patterns: list[str]) -> list[re.Pattern]:
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p))
        except re.error:
            pass
    return compiled


def _matches_any(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)
