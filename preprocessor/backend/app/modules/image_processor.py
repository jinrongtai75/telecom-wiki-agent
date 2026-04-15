import base64
import json
import uuid
from pathlib import Path

from app.models import DocumentObject
from app.modules.llm_client import call_llm, call_vlm

IMAGES_DIR = Path(__file__).parent.parent.parent / "images"


class ImageProcessor:
    def __init__(self):
        IMAGES_DIR.mkdir(exist_ok=True)

    def save_and_link(self, image_object: DocumentObject, target_text: str, save_dir: str = "") -> DocumentObject:
        save_path = Path(save_dir) if save_dir else IMAGES_DIR
        save_path.mkdir(parents=True, exist_ok=True)

        content = image_object.content
        if content.startswith("data:image"):
            header, b64data = content.split(",", 1)
            ext = header.split("/")[1].split(";")[0]
            filename = f"{image_object.id}.{ext}"
            filepath = save_path / filename
            filepath.write_bytes(base64.b64decode(b64data))
            image_path = f"/images/{filename}"
        else:
            image_path = content

        image_object.image_path = image_path
        image_object.processed_content = f"{target_text} <{image_path}>"
        image_object.metadata["alt"] = target_text
        image_object.metadata["image_mode"] = "link"
        return image_object

    def review_with_vlm(self, image_content: str) -> dict:
        """이미지를 분석해 처리 방식 결정
        반환:
          {"action": "discard"}
          {"action": "save", "description": "이미지 설명"}
          {"action": "describe", "result": "텍스트 설명"}
        """
        prompt = (
            "당신은 기업 RAG(검색 증강 생성) 파이프라인의 문서 전처리 전문가입니다.\n"
            "아래 이미지를 분석하여 반드시 2단계 판단 트리에 따라 처리 방식을 결정하세요.\n\n"

            "━━ 판단 트리 ━━\n"
            "STEP 1. 이미지에 의미 있는 정보가 있는가?\n"
            "  → 없으면 discard\n"
            "  (해당 예시: 로고, 회사 CI, 구분선, 장식 도형, 빈 여백, 워터마크, 배경 패턴)\n\n"

            "STEP 2. 정보가 있다면, 텍스트만으로 완전히 재현 가능한가?\n"
            "  → 가능하면 describe (이미지 없이도 검색에서 동일하게 활용 가능)\n"
            "  (해당 예시: 숫자·텍스트 위주 표, 단계형 순서도, 항목 목록, 수식, 텍스트 다이어그램)\n\n"
            "  → 불가능하면 save (시각 정보 손실 없이 텍스트화 불가)\n"
            "  (해당 예시: 실사 사진, 스크린샷, 색상·크기가 의미를 가진 차트/그래프,\n"
            "   공간 배치가 중요한 지도·도면·아키텍처 다이어그램)\n\n"

            "━━ 출력 형식 ━━\n"
            '{"action": "discard"}\n'
            '{"action": "save", "description": "이미지 내용 한 줄 요약 (검색 키워드 포함)"}\n'
            '{"action": "describe", "result": "이미지의 모든 정보를 빠짐없이 자연어로 서술. 수치·항목·관계를 명시"}\n\n'

            "반드시 JSON만 출력하세요. 설명, 마크다운 코드블록 금지."
        )
        try:
            raw = call_vlm(image_content, prompt, max_tokens=1000)
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"VLM API 호출 실패: {e}")

    def interpret_with_vlm(self, image_object: DocumentObject) -> DocumentObject:
        """VLM으로 이미지 해석 + 이미지 파일 저장. processed_content와 image_path를 모두 업데이트."""
        description = call_vlm(image_object.content, "이 이미지의 내용을 상세히 설명해주세요.", max_tokens=2000)
        image_object.processed_content = description

        # 이미지 파일 저장
        content = image_object.content
        if content.startswith("data:image"):
            header, b64data = content.split(",", 1)
            ext = header.split("/")[1].split(";")[0]
            filename = f"{image_object.id}.{ext}"
            filepath = IMAGES_DIR / filename
            filepath.write_bytes(base64.b64decode(b64data))
            image_object.image_path = f"/images/{filename}"
            image_object.metadata["image_mode"] = "interpret"
            if "alt" not in image_object.metadata:
                image_object.metadata["alt"] = image_object.id

        return image_object

    def chat_edit(self, current_text: str, user_request: str) -> str:
        prompt = f"다음 텍스트를 아래 요청에 따라 수정해주세요.\n\n텍스트:\n{current_text}\n\n요청:\n{user_request}"
        return call_llm(prompt, max_tokens=500)
