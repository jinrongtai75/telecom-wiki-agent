"""
앱 설정 API — API 키 관리 (JIHYE 게이트웨이 토큰 등).
preprocessor 백엔드의 /api/settings/keys 와 동일한 인터페이스를 제공하여
두 서비스 간 토큰 공유를 지원합니다.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import get_db
from app.models.db_models import AppSetting, User
from app.security.auth_deps import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])

SUPPORTED_SERVICES = {"jihye", "gemini"}


class SaveKeyRequest(BaseModel):
    service: str    # "JIHYE"
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

    if svc == "jihye":
        try:
            resp = httpx.post(
                app_settings.jihye_gateway_url,
                headers={
                    "Authorization": f"Bearer {setting.value}",
                    "anthropic-version": "bedrock-2023-05-31",
                    "Content-Type": "application/json",
                },
                json={
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                timeout=15,
            )
            if resp.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JIHYE 토큰이 유효하지 않습니다",
                )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"JIHYE 게이트웨이 연결 실패: {e}",
            ) from e
    elif svc == "gemini":
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
