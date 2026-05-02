import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.modules.api_key_manager import APIKeyManager
from app.modules.llm_client import _ENDPOINT, _headers

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


@router.get('/jihye/ping')
async def ping_jihye():
    """JIHYE 게이트웨이 실제 LLM 호출 테스트 (Railway→JIHYE 연결 가능 여부 확인)."""
    try:
        resp = httpx.post(
            _ENDPOINT,
            headers=_headers(),
            json={"anthropic_version": "bedrock-2023-05-31", "max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]},
            timeout=20,
        )
        return {"status": resp.status_code, "reachable": resp.status_code < 500, "body_preview": resp.text[:200]}
    except httpx.TimeoutException:
        return {"reachable": False, "error": "timeout (20s)"}
    except Exception as e:
        return {"reachable": False, "error": str(e)}
