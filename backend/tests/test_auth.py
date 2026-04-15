import os as _os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as db_module
from app.database import Base, get_db
from app.main import app
from app.security.jwt_handler import hash_password

# 테스트용 파일 DB
_TEST_DB_PATH = _os.path.join(_os.path.dirname(__file__), "..", "test_telecom.db")
TEST_DB_URL = f"sqlite:///{_TEST_DB_PATH}"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True, scope="module")
def setup_test_db():
    db_module.engine = test_engine
    db_module.SessionLocal = TestSessionLocal
    Base.metadata.create_all(bind=test_engine)

    # 테스트용 admin 계정 직접 생성
    from app.models.db_models import User
    db = TestSessionLocal()
    admin = User(username="admin", hashed_password=hash_password("admin123"), is_admin=True)
    db.add(admin)
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)
    if _os.path.exists(_TEST_DB_PATH):
        _os.remove(_TEST_DB_PATH)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def get_admin_token() -> str:
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    return res.json()["access_token"]


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["is_admin"] is True


def test_login_wrong_password():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


def test_register_endpoint_removed():
    """회원가입 엔드포인트는 제거되어야 한다."""
    res = client.post("/api/auth/register", json={"username": "someone", "password": "pass123"})
    assert res.status_code == 404


def test_admin_create_user():
    token = get_admin_token()
    res = client.post(
        "/api/admin/users",
        json={"username": "user_a", "password": "pass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["username"] == "user_a"
    assert res.json()["is_admin"] is False


def test_admin_create_user_duplicate():
    token = get_admin_token()
    client.post(
        "/api/admin/users",
        json={"username": "dup_user", "password": "pass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    res = client.post(
        "/api/admin/users",
        json={"username": "dup_user", "password": "pass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 409


def test_admin_list_users():
    token = get_admin_token()
    res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    usernames = [u["username"] for u in res.json()]
    assert "admin" in usernames


def test_admin_delete_user():
    token = get_admin_token()
    # 삭제할 유저 생성
    create_res = client.post(
        "/api/admin/users",
        json={"username": "to_delete", "password": "pass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = create_res.json()["id"]
    # 삭제
    res = client.delete(f"/api/admin/users/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204


def test_non_admin_cannot_create_user():
    token = get_admin_token()
    # 일반 유저 생성
    client.post(
        "/api/admin/users",
        json={"username": "normal_user", "password": "pass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 일반 유저 토큰으로 로그인
    user_token = client.post(
        "/api/auth/login", json={"username": "normal_user", "password": "pass123"}
    ).json()["access_token"]
    # 관리자 엔드포인트 접근 시도 → 403
    res = client.post(
        "/api/admin/users",
        json={"username": "hacked", "password": "pass123"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res.status_code == 403


def test_created_user_can_login():
    token = get_admin_token()
    client.post(
        "/api/admin/users",
        json={"username": "login_test_user", "password": "mypass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    res = client.post(
        "/api/auth/login", json={"username": "login_test_user", "password": "mypass123"}
    )
    assert res.status_code == 200
    assert "access_token" in res.json()
