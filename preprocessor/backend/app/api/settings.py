import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.modules.api_key_manager import APIKeyManager

router = APIRouter(prefix='/api/settings', tags=['settings'])
key_mgr = APIKeyManager()


class KeyRequest(BaseModel):
    service: str
    api_key: str


class ValidateRequest(BaseModel):
    service: str


@router.get('/keys')
async def list_keys():
    return key_mgr.list_services()


@router.post('/keys')
async def save_key(body: KeyRequest):
    key_mgr.save_key(body.service, body.api_key)
    return {'message': f'{body.service} API 키가 저장되었습니다'}


@router.post('/keys/validate')
async def validate_key(body: ValidateRequest):
    valid = key_mgr.validate_key(body.service)
    if not valid:
        raise HTTPException(status_code=400, detail='API 키가 유효하지 않습니다. 설정에서 확인해주세요')
    return {'valid': True, 'service': body.service}


@router.get('/gemini/ping')
async def ping_gemini():
    """Gemini API 연결 테스트."""
    from app.modules.llm_client import _get_api_key  # noqa: PLC0415
    key = _get_api_key()
    if not key:
        return {"reachable": False, "error": "Gemini API 키 미설정"}
    try:
        resp = httpx.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
            timeout=10,
        )
        return {"status": resp.status_code, "reachable": resp.status_code == 200}
    except httpx.TimeoutException:
        return {"reachable": False, "error": "timeout (10s)"}
    except Exception as e:
        return {"reachable": False, "error": str(e)}
