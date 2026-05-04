"""
앱 설정 API — API 키 관리 (Gemini API 키 등).
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import AppSetting, User
from app.security.auth_deps import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])

SUPPORTED_SERVICES = {"gemini"}


class SaveKeyRequest(BaseModel):
    service: str    # "GEMINI"
    api_key: str


class ValidateKeyRequest(BaseModel):
    service: str


def _setting_key(service: str) -> str:
    return service.lower() + "_token"


@router.get("/keys")
def list_keys(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """등록된 API 키 현황 반환 (키값 노출 없이 등록 여부만)."""
    result: dict[str, bool] = {}
    for svc in SUPPORTED_SERVICES:
        setting = db.get(AppSetting, _setting_key(svc))
        result[svc] = bool(setting and setting.value)
    return result


@router.post("/keys", status_code=status.HTTP_200_OK)
def save_key(
    body: SaveKeyRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """API 키 저장."""
    svc = body.service.lower()
    if svc not in SUPPORTED_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 서비스: {body.service}",
        )
    key = _setting_key(svc)
    existing = db.get(AppSetting, key)
    if existing:
        existing.value = body.api_key
    else:
        db.add(AppSetting(key=key, value=body.api_key))
    db.commit()
    return {"saved": True, "service": body.service}


@router.post("/keys/validate", status_code=status.HTTP_200_OK)
def validate_key(
    body: ValidateKeyRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """저장된 API 키의 유효성 검증."""
    svc = body.service.lower()
    setting = db.get(AppSetting, _setting_key(svc))
    if not setting or not setting.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="키가 등록되지 않았습니다",
        )

    if svc == "gemini":
        try:
            resp = httpx.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={setting.value}",
                timeout=10,
            )
            if resp.status_code in (401, 403):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Gemini API 키가 유효하지 않습니다",
                )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Gemini API 연결 실패: {e}",
            ) from e

    return {"valid": True, "service": body.service}


@router.post("/vector-store/reset", status_code=status.HTTP_200_OK)
def reset_vector_store(
    current_user: User = Depends(get_current_user),
):
    """ChromaDB 컬렉션 초기화 (관리자 전용). 임베딩 모델 변경 후 사용."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자만 실행 가능합니다")
    from app.modules import vector_store  # noqa: PLC0415
    return vector_store.reset_collection()


class SetLlmModeRequest(BaseModel):
    mode: str  # "fast" | "thinking"


@router.get("/llm-mode")
def get_llm_mode(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    setting = db.get(AppSetting, "llm_thinking_mode")
    return {"mode": setting.value if setting else "fast"}


@router.post("/llm-mode")
def set_llm_mode(
    body: SetLlmModeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자만 변경 가능합니다")
    if body.mode not in ("fast", "thinking"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode는 'fast' 또는 'thinking'이어야 합니다")
    existing = db.get(AppSetting, "llm_thinking_mode")
    if existing:
        existing.value = body.mode
    else:
        db.add(AppSetting(key="llm_thinking_mode", value=body.mode))
    db.commit()
    return {"mode": body.mode}
