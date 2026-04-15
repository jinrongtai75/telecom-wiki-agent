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
