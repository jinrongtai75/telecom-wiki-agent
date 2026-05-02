"""
TDD: preprocessor ingest 엔드포인트 테스트
- 비밀번호 미설정 → 503
- 잘못된 비밀번호 → 502 (Wiki Agent 로그인 실패: 401)
- 정상 적재 → 200 chunk_count
- /check 엔드포인트 → 연결 상태 확인
"""
from __future__ import annotations

import os
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── APIKeyManager ─────────────────────────────────────────────────────────────

class TestAPIKeyManager:
    def test_wiki_password_not_set_by_default(self, monkeypatch):
        """환경변수 없으면 wiki 비밀번호 None."""
        monkeypatch.delenv("WIKI_AGENT_PASSWORD", raising=False)
        from app.modules.api_key_manager import APIKeyManager
        mgr = APIKeyManager()
        # .env 파일에도 없고 환경변수도 없으면 None
        assert mgr.get_key("WIKI_AGENT_PASSWORD") is None

    def test_wiki_password_from_env(self, monkeypatch):
        """환경변수가 있으면 읽혀야 한다."""
        monkeypatch.setenv("WIKI_AGENT_PASSWORD", "testpass")
        from app.modules.api_key_manager import APIKeyManager
        mgr = APIKeyManager()
        assert mgr.get_key("WIKI_AGENT_PASSWORD") == "testpass"

    def test_list_services_includes_wiki_agent_false(self, monkeypatch):
        """비밀번호 없으면 wiki_agent: False."""
        monkeypatch.delenv("WIKI_AGENT_PASSWORD", raising=False)
        from app.modules.api_key_manager import APIKeyManager
        mgr = APIKeyManager()
        result = mgr.list_services()
        assert "wiki_agent" in result
        assert result["wiki_agent"] is False

    def test_list_services_includes_wiki_agent_true(self, monkeypatch):
        """비밀번호 있으면 wiki_agent: True."""
        monkeypatch.setenv("WIKI_AGENT_PASSWORD", "somepass")
        from app.modules.api_key_manager import APIKeyManager
        mgr = APIKeyManager()
        result = mgr.list_services()
        assert result["wiki_agent"] is True


# ── Ingest 엔드포인트 ──────────────────────────────────────────────────────────

FORM_DATA = {
    "filename": "test.md",
    "content": "# Test\nsome content",
    "source_name": "test.md",
}


class TestIngestEndpoint:
    def test_no_password_returns_503(self, monkeypatch):
        """비밀번호 미설정 → 503 + 명확한 한국어 메시지."""
        monkeypatch.delenv("WIKI_AGENT_PASSWORD", raising=False)
        with patch("app.api.ingest._get_wiki_pass", return_value=""):
            res = client.post("/api/ingest/to-wiki", data=FORM_DATA)
        assert res.status_code == 503
        assert "비밀번호" in res.json()["detail"]

    def test_wrong_password_returns_502(self, monkeypatch):
        """잘못된 비밀번호 → 502 + 'Wiki Agent 로그인 실패: 401' 메시지."""
        login_response = MagicMock()
        login_response.status_code = 401
        login_error = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=login_response
        )

        with patch("app.api.ingest._get_wiki_pass", return_value="wrongpass"), \
             patch("app.api.ingest._get_wiki_token", new_callable=AsyncMock,
                   side_effect=login_error):
            res = client.post("/api/ingest/to-wiki", data=FORM_DATA)

        assert res.status_code == 502
        assert "401" in res.json()["detail"]

    def test_success_returns_chunk_count(self):
        """정상 자격증명 + 적재 성공 → chunk_count 반환."""
        ingest_response = MagicMock()
        ingest_response.status_code = 200
        ingest_response.json.return_value = {"doc_id": "abc", "chunk_count": 15, "has_pdf": False}
        ingest_response.raise_for_status = MagicMock()

        async def mock_post(*args, **kwargs):
            return ingest_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch("app.api.ingest._get_wiki_pass", return_value="Lguplus2026"), \
             patch("app.api.ingest._get_wiki_token", new_callable=AsyncMock,
                   return_value="mock-jwt-token"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            res = client.post("/api/ingest/to-wiki", data=FORM_DATA)

        assert res.status_code == 200
        assert res.json()["chunk_count"] == 15


# ── Check 엔드포인트 (아직 없음 → RED) ────────────────────────────────────────

class TestCheckEndpoint:
    def test_check_endpoint_exists(self):
        """/api/ingest/check 엔드포인트가 존재해야 한다."""
        res = client.get("/api/ingest/check")
        assert res.status_code != 404

    def test_check_no_password_returns_error_status(self):
        """비밀번호 없으면 check가 ok:False를 반환해야 한다."""
        with patch("app.api.ingest._get_wiki_pass", return_value=""):
            res = client.get("/api/ingest/check")
        assert res.status_code == 200
        assert res.json()["ok"] is False
        assert "password" in res.json()["error"].lower() or "비밀번호" in res.json()["error"]

    def test_check_wrong_credentials_returns_error_status(self):
        """잘못된 자격증명이면 check가 ok:False + login_status:401을 반환해야 한다."""
        login_response = MagicMock()
        login_response.status_code = 401

        async def mock_post(*args, **kwargs):
            raise httpx.HTTPStatusError("401", request=MagicMock(), response=login_response)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch("app.api.ingest._get_wiki_pass", return_value="wrongpass"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            res = client.get("/api/ingest/check")

        assert res.status_code == 200
        assert res.json()["ok"] is False
        assert res.json()["login_status"] == 401

    def test_check_valid_credentials_returns_ok(self):
        """유효한 자격증명이면 check가 ok:True를 반환해야 한다."""
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {"access_token": "mock-token"}
        login_response.raise_for_status = MagicMock()

        async def mock_post(*args, **kwargs):
            return login_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch("app.api.ingest._get_wiki_pass", return_value="Lguplus2026"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            res = client.get("/api/ingest/check")

        assert res.status_code == 200
        assert res.json()["ok"] is True
