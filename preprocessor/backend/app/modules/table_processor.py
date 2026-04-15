import io
import json
import pandas as pd

from app.models import DocumentObject
from app.modules.llm_client import call_llm, call_vlm


class TableProcessor:
    def to_dataframe(self, table_object: DocumentObject) -> str:
        content = table_object.processed_content or table_object.content
        lines = [l for l in content.strip().splitlines() if l.strip()]
        rows = []
        for line in lines:
            if set(line.replace("|", "").replace("-", "").replace(" ", "")) == set():
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
        if not rows:
            return content
        try:
            df = pd.DataFrame(rows[1:], columns=rows[0])
            return df.to_markdown(index=False)
        except Exception:
            return content

    def flatten_with_llm(self, table_object: DocumentObject) -> str:
        content = table_object.processed_content or table_object.content
        prompt = (
            "다음은 문서에서 추출한 표입니다.\n"
            "이 표의 내용을 RAG(검색 증강 생성) 시스템에서 활용할 수 있도록 "
            "정보 손실 없이 자연어 문장으로 변환해주세요.\n\n"
            "규칙:\n"
            "- 표의 모든 항목과 값을 빠짐없이 포함할 것\n"
            "- 항목 간 관계가 명확하게 드러나도록 작성할 것\n"
            "- 불필요한 설명이나 서두 없이 본문만 출력할 것\n\n"
            f"표:\n{content}"
        )
        return call_llm(prompt, max_tokens=1000)

    def review_with_vlm(self, image_b64: str, parsed_content: str) -> dict:
        """표 이미지와 파싱 결과를 비교해 단순하면 keep, 복잡하면 flatten 결과 반환"""
        prompt = (
            "아래는 이 표를 자동 파싱한 결과입니다:\n\n"
            f"{parsed_content}\n\n"
            "---\n"
            "위 표 이미지와 파싱 결과를 비교하여 다음 기준으로 판단하세요:\n\n"
            "판단 기준:\n"
            "- 파싱 결과가 표의 모든 셀 값을 정확하게 담고 있으면 → keep\n"
            "- 셀 병합, 다중 헤더, 누락된 값 등으로 파싱이 불완전하면 → flatten\n\n"
            'keep이면: {"action": "keep"}\n'
            'flatten이면: {"action": "flatten", "result": "표 전체 내용을 정보 손실 없이 자연어로 변환한 텍스트"}\n\n'
            "반드시 JSON만 출력하세요. 다른 설명은 금지."
        )
        try:
            raw = call_vlm(image_b64, prompt, max_tokens=1500)
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"VLM API 호출 실패: {e}")

    def review_with_llm(self, parsed_content: str) -> dict:
        """DOCX 등 이미지 없는 경우: 파싱된 마크다운만으로 표 품질 판단"""
        prompt = (
            "다음은 문서에서 자동 파싱된 표입니다:\n\n"
            f"{parsed_content}\n\n"
            "---\n"
            "아래 기준으로 판단하세요:\n"
            "- 표 구조가 명확하고 모든 값이 올바르게 파싱된 경우 → keep\n"
            "- 셀 값 누락, 헤더 오인식, 구조 손상 등이 의심되는 경우 → flatten\n\n"
            'keep이면: {"action": "keep"}\n'
            'flatten이면: {"action": "flatten", "result": "표 전체 내용을 정보 손실 없이 자연어로 변환한 텍스트"}\n\n'
            "반드시 JSON만 출력하세요. 다른 설명은 금지."
        )
        try:
            raw = call_llm(prompt, max_tokens=1000)
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"LLM API 호출 실패: {e}")

    def flatten_with_vlm(self, image_b64: str) -> str:
        """PDF에서 크롭한 표 이미지를 VLM으로 직접 분석해 자연어로 변환"""
        prompt = (
            "이 이미지는 문서에서 추출한 표입니다.\n"
            "표의 내용을 RAG(검색 증강 생성) 시스템에서 활용할 수 있도록 "
            "정보 손실 없이 자연어 문장으로 변환해주세요.\n\n"
            "규칙:\n"
            "- 셀 병합 여부와 관계없이 모든 항목과 값을 빠짐없이 포함할 것\n"
            "- 항목 간 관계가 명확하게 드러나도록 작성할 것\n"
            "- 불필요한 설명이나 서두 없이 본문만 출력할 것"
        )
        return call_vlm(image_b64, prompt, max_tokens=1000)

    def chat_edit(self, current_text: str, user_request: str) -> str:
        prompt = f"다음 텍스트를 아래 요청에 따라 수정해주세요.\n\n텍스트:\n{current_text}\n\n요청:\n{user_request}"
        return call_llm(prompt, max_tokens=1000)
