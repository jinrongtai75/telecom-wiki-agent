from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import User
from app.models.schemas import InitAdminRequest, LoginRequest, TokenResponse
from app.security.jwt_handler import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user.id, user.is_admin)
    return TokenResponse(access_token=token, is_admin=user.is_admin)


@router.post("/init-admin", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def init_admin(req: InitAdminRequest, db: Session = Depends(get_db)):
    """최초 관리자 계정 생성 엔드포인트.

    데이터베이스에 사용자가 한 명도 없을 때만 동작합니다.
    관리자가 이미 존재하면 409 Conflict를 반환합니다.
    """
    user_count = db.query(User).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 초기화된 시스템입니다. 관리자 계정이 존재합니다.",
        )

    admin = User(
        username=req.username,
        hashed_password=hash_password(req.password),
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    token = create_access_token(admin.id, is_admin=True)
    return TokenResponse(access_token=token, is_admin=True)
