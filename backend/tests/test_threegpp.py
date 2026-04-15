from app.modules.threegpp import search_3gpp


def test_search_5g_keywords():
    results = search_3gpp(["5G", "handover", "NR"])
    assert len(results) > 0
    # 5G NR 관련 38 시리즈가 포함되어야 함
    assert any(r.series == "38" for r in results)


def test_search_lte_keywords():
    results = search_3gpp(["LTE", "RRC"])
    assert len(results) > 0
    assert any("36" in r.spec_number or r.series == "36" for r in results)


def test_search_direct_spec_number():
    results = search_3gpp(["38.331 RRC 절차"])
    assert any(r.spec_number == "38.331" for r in results)


def test_search_unknown_keywords():
    # 알 수 없는 키워드도 기본 결과 반환
    results = search_3gpp(["unknown_keyword_xyz"])
    assert len(results) > 0


def test_max_results():
    results = search_3gpp(["5G"], max_results=3)
    assert len(results) <= 3
