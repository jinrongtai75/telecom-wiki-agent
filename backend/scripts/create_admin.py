#!/usr/bin/env python3
"""
관리자 계정 초기 생성 스크립트.
Usage:
    uv run python scripts/create_admin.py
    uv run python scripts/create_admin.py --username admin --password mypassword
"""
import argparse
import os
import sys

# backend/ 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, create_tables
from app.models.db_models import User
from app.security.jwt_handler import hash_password


def create_admin(username: str, password: str) -> None:
    create_tables()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            if existing.is_admin:
                print(f"✅ 관리자 계정 '{username}'이 이미 존재합니다.")
            else:
                existing.is_admin = True
                db.commit()
                print(f"✅ '{username}' 계정을 관리자로 승격했습니다.")
            return

        admin = User(
            username=username,
            hashed_password=hash_password(password),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        print(f"✅ 관리자 계정 생성 완료: {username}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="관리자 계정 생성")
    parser.add_argument("--username", default="admin", help="관리자 아이디 (기본: admin)")
    parser.add_argument("--password", default=None, help="패스워드 (미입력 시 대화형 입력)")
    args = parser.parse_args()

    password = args.password
    if not password:
        import getpass
        password = getpass.getpass(f"패스워드 입력 ({args.username}): ")
        confirm = getpass.getpass("패스워드 확인: ")
        if password != confirm:
            print("❌ 패스워드가 일치하지 않습니다.")
            sys.exit(1)

    if len(password) < 6:
        print("❌ 패스워드는 6자 이상이어야 합니다.")
        sys.exit(1)

    create_admin(args.username, password)


if __name__ == "__main__":
    main()
