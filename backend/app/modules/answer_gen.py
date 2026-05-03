"""
RAG 답변 생성 모듈.
검색된 컨텍스트 + 사용자 질문 → LLM 답변 생성.
"""
from __future__ import annotations

from app.modules.llm_client import LLMClient
from app.modules.threegpp import ThreeGppResult

SYSTEM_PROMPT = """당신은 LGU+ 무선통신 프로토콜 전문가입니다.
LTE/5G NR, 3GPP 규격, 단말 프로토콜 스택에 대한 깊은 지식을 가지고 있습니다.

답변 규칙:
1. 제공된 컨텍스트(문서 내용)를 우선 참조하세요
2. 출처를 반드시 [출처: 문서명 p.N] 형식으로 인용하세요
3. 전문 용어는 정확하게 사용하되 HW 엔지니어도 이해할 수 있게 설명하세요
4. 마크다운 형식 사용 가능 (제목, 목록, 코드블록)
5. 확실하지 않은 내용은 "확인 필요" 또는 "3GPP 규격 직접 참조 권장"으로 명시하세요"""


def generate_answer(
    question: str,
    chunks: list[dict],
    llm_client: LLMClient,
    threegpp_results: list[ThreeGppResult] | None = None,
) -> str:
    """
    chunks: vector_store.search() 반환값
    threegpp_results: 3GPP 폴백 결과 (없으면 None)
    """
    if chunks:
        prompt = _build_rag_prompt(question, chunks)
    elif threegpp_results:
        prompt = _build_3gpp_prompt(question, threegpp_results)
    else:
        prompt = _build_fallback_prompt(question)

    return llm_client.complete(prompt, system=SYSTEM_PROMPT)


def extract_keywords(question: str, llm_client: LLMClient) -> list[str]:
    """질문에서 검색 키워드 추출 (한국어 → 영어 기술 용어)."""
    prompt = f"""다음 질문에서 3GPP/LTE/5G 검색에 사용할 핵심 영어 기술 키워드를 추출하세요.
키워드만 쉼표로 구분하여 출력하세요 (설명 없이).

질문: {question}

키워드 (영어, 최대 5개):"""

    try:
        result = llm_client.complete(prompt, max_tokens=100)
        return [k.strip() for k in result.split(",") if k.strip()]
    except Exception:
        # LLM 실패 시 질문 단어 그대로 사용
        return question.split()[:5]


def _build_rag_prompt(question: str, chunks: list[dict]) -> str:
    context_parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        source = f"[출처: {chunk.get('doc_id', 'unknown')} p.{chunk.get('page', '?')}]"
        section = chunk.get("section", "")
        content = chunk.get("content", "")
        context_parts.append(f"--- 컨텍스트 {i} {source} ---\n섹션: {section}\n{content}")

    context = "\n\n".join(context_parts)
    return f"""다음 문서 컨텍스트를 바탕으로 질문에 답변하세요.

{context}

---

질문: {question}

답변:"""


def _build_3gpp_prompt(question: str, results: list[ThreeGppResult]) -> str:
    refs = "\n".join(
        f"- {r.spec_number}: {r.title} ({r.url})"
        for r in results
    )
    return f"""내부 문서에서 관련 내용을 찾지 못했습니다.
아래 3GPP 공식 규격서를 참고하여 답변하세요.

관련 3GPP 규격:
{refs}

---

질문: {question}

3GPP 표준 지식을 바탕으로 답변하되, 정확한 내용은 해당 규격서를 직접 확인하도록 안내하세요:"""


def _build_fallback_prompt(question: str) -> str:
    return f"""내부 문서와 3GPP 참조 자료에서 관련 내용을 찾지 못했습니다.
무선통신 프로토콜 전문 지식을 바탕으로 최선을 다해 답변하되,
불확실한 내용은 명확히 표시하고 3GPP 규격 직접 확인을 권장하세요.

질문: {question}

답변:"""
