"""
3GPP FTP 폴백 검색 모듈.
무선통신프로토콜 프로젝트의 ThreeGppSearchService.java를 Python으로 포팅.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

# 주요 3GPP 시리즈 매핑 (키워드 → 시리즈)
SERIES_MAP: dict[str, list[str]] = {
    "5g": ["38"],
    "nr": ["38"],
    "lte": ["36"],
    "4g": ["36"],
    "ims": ["24", "23"],
    "sip": ["24"],
    "core": ["23"],
    "ran": ["38", "36"],
    "mac": ["38"],
    "rrc": ["38"],
    "pdcp": ["38"],
    "rlc": ["38"],
    "ngap": ["38"],
    "nas": ["24"],
    "handover": ["38", "36"],
    "handoff": ["38", "36"],
    "attach": ["24"],
    "pdu": ["23", "38"],
}

# 잘 알려진 3GPP 규격서 목록
CURATED_SPECS: list[dict] = [
    {"series": "38", "number": "38.331", "title": "NR RRC protocol specification"},
    {"series": "38", "number": "38.300", "title": "NR Overall description"},
    {"series": "38", "number": "38.201", "title": "NR Physical layer general description"},
    {"series": "38", "number": "38.213", "title": "NR Physical layer procedures for control"},
    {"series": "38", "number": "38.214", "title": "NR Physical layer procedures for data"},
    {"series": "38", "number": "38.401", "title": "NG-RAN Architecture description"},
    {"series": "38", "number": "38.413", "title": "NG Application Protocol (NGAP)"},
    {"series": "36", "number": "36.331", "title": "LTE RRC protocol specification"},
    {"series": "36", "number": "36.300", "title": "LTE Overall description"},
    {"series": "23", "number": "23.501", "title": "System architecture for 5G (5GS)"},
    {"series": "23", "number": "23.502", "title": "Procedures for the 5G System"},
    {"series": "24", "number": "24.301", "title": "NAS protocol for EPS"},
    {"series": "24", "number": "24.501", "title": "NAS protocol for 5GS"},
]

THREEGPP_FTP_BASE = "https://www.3gpp.org/ftp/Specs/archive"


@dataclass
class ThreeGppResult:
    spec_number: str
    title: str
    url: str
    series: str


def search_3gpp(keywords: list[str], max_results: int = 5) -> list[ThreeGppResult]:
    """
    키워드 기반 3GPP 규격서 검색.
    FTP 직접 접근 없이 큐레이션된 목록과 키워드 매칭.
    """
    lower_kw = [k.lower() for k in keywords]

    # 관련 시리즈 수집
    relevant_series: set[str] = set()
    for kw in lower_kw:
        for key, series_list in SERIES_MAP.items():
            if key in kw:
                relevant_series.update(series_list)

    # 기본값: 38 시리즈 (5G NR)
    if not relevant_series:
        relevant_series.add("38")

    # 규격 번호 직접 언급 (예: "38.331")
    spec_re = re.compile(r"\b(\d{2}\.\d{3,5})\b")
    direct_specs: set[str] = set()
    for kw in lower_kw:
        for m in spec_re.finditer(kw):
            direct_specs.add(m.group(1))

    results: list[ThreeGppResult] = []

    # 직접 언급된 규격 우선
    for spec_num in direct_specs:
        for spec in CURATED_SPECS:
            if spec["number"] == spec_num:
                results.append(ThreeGppResult(
                    spec_number=spec["number"],
                    title=spec["title"],
                    url=_make_url(spec["number"]),
                    series=spec["series"],
                ))
                break

    # 시리즈 기반 매칭
    for spec in CURATED_SPECS:
        if spec["series"] in relevant_series and len(results) < max_results:
            # 이미 추가된 스펙 중복 방지
            if not any(r.spec_number == spec["number"] for r in results):
                # 제목에 키워드 포함 여부로 추가 필터링
                title_lower = spec["title"].lower()
                if any(kw in title_lower for kw in lower_kw) or not lower_kw:
                    results.append(ThreeGppResult(
                        spec_number=spec["number"],
                        title=spec["title"],
                        url=_make_url(spec["number"]),
                        series=spec["series"],
                    ))

    # 키워드 매칭 없어도 기본 결과 제공
    if not results:
        for spec in CURATED_SPECS[:max_results]:
            results.append(ThreeGppResult(
                spec_number=spec["number"],
                title=spec["title"],
                url=_make_url(spec["number"]),
                series=spec["series"],
            ))

    return results[:max_results]


def _make_url(spec_number: str) -> str:
    """3GPP FTP URL 생성."""
    parts = spec_number.split(".")
    if len(parts) == 2:
        series = parts[0]
        return f"{THREEGPP_FTP_BASE}/{series}_series/{spec_number}/"
    return f"https://www.3gpp.org/DynaReport/{spec_number}.htm"


def check_3gpp_available() -> bool:
    """3GPP 서버 접근 가능 여부 확인."""
    try:
        r = httpx.get("https://www.3gpp.org", timeout=5)
        return r.status_code < 500
    except Exception:
        return False
