"""
파일 스토리지 추상화 레이어.

로컬(개발) ↔ Supabase Storage(운영) 전환을 환경변수 하나로 처리.

사용 키 규칙:
  documents/{doc_id}.pdf   — 원본 PDF
  markdowns/{doc_id}.md    — MD 파일

사용법:
  from app.services.storage_service import get_storage

  storage = get_storage()
  storage.save("documents/abc.pdf", pdf_bytes)
  pdf_bytes = storage.load("documents/abc.pdf")
  storage.delete("documents/abc.pdf")
  storage.exists("documents/abc.pdf")
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


# ── 추상 인터페이스 ──────────────────────────────────────────────────────────

class StorageService(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> None:
        """키 경로에 바이트 저장 (덮어쓰기)."""
        ...

    @abstractmethod
    def load(self, key: str) -> bytes:
        """키 경로의 파일을 바이트로 반환. 없으면 FileNotFoundError."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """키 경로의 파일 삭제. 없어도 예외 없음."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """키 경로에 파일이 존재하는지 확인."""
        ...


# ── 로컬 파일시스템 구현 ──────────────────────────────────────────────────────

class LocalStorageService(StorageService):
    """개발·온프레미스용. ./data 아래에 키 그대로 저장."""

    def __init__(self, base_path: str = "./data") -> None:
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.base / key

    def save(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def load(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        return p.read_bytes()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


# ── Supabase Storage 구현 ────────────────────────────────────────────────────

class SupabaseStorageService(StorageService):
    """
    Supabase Storage 백엔드.
    필요 패키지: uv add supabase

    버킷 설정:
      - Supabase 대시보드 → Storage → New bucket
      - Private 버킷 권장 (RLS 없이 service_role 키로만 접근)
    """

    def __init__(self, url: str, key: str, bucket: str) -> None:
        try:
            from supabase import create_client  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "Supabase 패키지가 설치되지 않았습니다. 'uv add supabase' 실행 후 재시작하세요."
            ) from exc
        self.client = create_client(url, key)
        self.bucket = bucket

    def save(self, key: str, data: bytes) -> None:
        # upsert=True: 동일 키 재업로드 허용
        self.client.storage.from_(self.bucket).upload(
            path=key,
            file=data,
            file_options={"upsert": "true"},
        )

    def load(self, key: str) -> bytes:
        try:
            return bytes(self.client.storage.from_(self.bucket).download(key))
        except Exception as exc:
            raise FileNotFoundError(f"Storage key not found: {key}") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.storage.from_(self.bucket).remove([key])
        except Exception:
            pass  # 없는 파일 삭제는 무시

    def exists(self, key: str) -> bool:
        try:
            self.client.storage.from_(self.bucket).download(key)
            return True
        except Exception:
            return False


# ── 팩토리 (싱글턴) ──────────────────────────────────────────────────────────

_storage: StorageService | None = None


def get_storage() -> StorageService:
    """
    환경변수 기반으로 스토리지 구현체를 반환 (최초 호출 시 초기화).

    SUPABASE_URL이 설정되어 있으면 SupabaseStorageService,
    없으면 LocalStorageService (./data 기준).
    """
    global _storage
    if _storage is None:
        from app.config import settings
        if settings.supabase_url:
            _storage = SupabaseStorageService(
                url=settings.supabase_url,
                key=settings.supabase_key,
                bucket=settings.supabase_bucket,
            )
        else:
            _storage = LocalStorageService(base_path="./data")
    return _storage
