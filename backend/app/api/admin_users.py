from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import User
from app.security.auth_deps import require_admin
from app.security.jwt_handler import hash_password

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


class UserInfo(BaseModel):
    id: str
    username: str
    is_admin: bool
    created_at: str

    @classmethod
    def from_orm(cls, user: User) -> "UserInfo":
        return cls(
            id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            created_at=user.created_at.isoformat(),
        )


class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not v or len(v) < 3 or len(v) > 50:
            raise ValueError("username must be 3-50 chars")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("password must be at least 6 chars")
        return v


@router.get("", response_model=list[UserInfo])
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.asc()).all()
    return [UserInfo.from_orm(u) for u in users]


@router.post("", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
def create_user(
    req: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 존재하는 아이디입니다")

    user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
        is_admin=req.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserInfo.from_orm(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="자기 자신은 삭제할 수 없습니다")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다")

    if target.is_admin:
        admin_count = db.query(User).filter(User.is_admin).count()
        if admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="마지막 관리자는 삭제할 수 없습니다")

    db.delete(target)
    db.commit()
