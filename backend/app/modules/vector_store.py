"""
ChromaDB 벡터 스토어.
- 임베딩: Gemini text-embedding-004 API (키 있으면) / 해시 폴백
- 로컬 모델/torch/onnxruntime 없음 — Railway 환경 안정성 확보
- 컬렉션: telecom_docs
"""
from __future__ import annotations

import hashlib
import os
from typing import List

import httpx
from chromadb import EmbeddingFunction, Documents, Embeddings

from app.config import settings
from app.modules.chunker import IndexChunk

COLLECTION_NAME = "telecom_docs"
GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents"

_chroma_client = None
_collection = None


class _GeminiEmbeddingFunction(EmbeddingFunction):
    """Gemini text-embedding-004 API 기반 임베딩."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    def __call__(self, input: Documents) -> Embeddings:
        requests_body = {
            "requests": [
                {"model": "models/text-embedding-004", "content": {"parts": [{"text": t}]}}
                for t in input
            ]
        }
        resp = httpx.post(
            f"{GEMINI_EMBED_URL}?key={self._key}",
            json=requests_body,
            timeout=60,
        )
        resp.raise_for_status()
        return [item["values"] for item in resp.json()["embeddings"]]


class _HashEmbeddingFunction(EmbeddingFunction):
    """API 키 없을 때 해시 기반 폴백 (768차원 pseudo-embedding)."""

    DIM = 768

    def __call__(self, input: Documents) -> Embeddings:
        result: Embeddings = []
        for text in input:
            digest = hashlib.sha256(text.encode()).digest()
            vec = [(b / 127.5) - 1.0 for b in digest]
            # 768차원 반복 채우기
            full = (vec * (self.DIM // len(vec) + 1))[: self.DIM]
            result.append(full)
        return result


def _make_embedding_function() -> EmbeddingFunction:
    """DB에 저장된 Gemini 키 → 없으면 해시 폴백."""
    try:
        from app.database import _get_session_local  # noqa: PLC0415
        from app.models.db_models import AppSetting  # noqa: PLC0415
        db = _get_session_local()()
        setting = db.get(AppSetting, "gemini_token")
        db.close()
        if setting and setting.value:
            return _GeminiEmbeddingFunction(setting.value)
    except Exception:
        pass
    return _HashEmbeddingFunction()


def _get_collection():
    import chromadb  # noqa: PLC0415

    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
    if _collection is None:
        ef = _make_embedding_function()
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def index_chunks(chunks: list[IndexChunk]) -> int:
    """청크를 ChromaDB에 인덱싱. 반환값: 인덱싱된 청크 수."""
    if not chunks:
        return 0

    collection = _get_collection()

    ids = [c.id for c in chunks]
    # e5 모델: 문서는 "passage: " 접두사
    documents = [f"passage: {c.content}" for c in chunks]
    metadatas = [
        {
            "doc_id": c.doc_id,
            "page": c.page,
            "section": c.section,
            "chunk_type": c.chunk_type,
            "image_path": c.image_path or "",
        }
        for c in chunks
    ]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks)


def search(query: str, top_k: int | None = None, doc_id: str | None = None) -> list[dict]:
    """
    의미 기반 검색.
    query: 사용자 질문 (자동으로 "query: " 접두사 추가)
    반환: [{"content", "doc_id", "page", "section", "chunk_type", "image_path", "score"}, ...]
    """
    if top_k is None:
        top_k = settings.search_top_k

    collection = _get_collection()

    where = {"doc_id": doc_id} if doc_id else None
    results = collection.query(
        query_texts=[f"query: {query}"],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits: list[dict] = []
    if not results["ids"] or not results["ids"][0]:
        return hits

    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # cosine distance → similarity (1 - distance)
        score = 1.0 - dist
        # "passage: " 접두사 제거
        content = doc[len("passage: "):] if doc.startswith("passage: ") else doc
        hits.append({
            "content": content,
            "doc_id": meta.get("doc_id", ""),
            "page": meta.get("page", 0),
            "section": meta.get("section", ""),
            "chunk_type": meta.get("chunk_type", "text"),
            "image_path": meta.get("image_path") or None,
            "score": round(score, 4),
        })

    return hits


def delete_doc(doc_id: str) -> int:
    """특정 문서의 모든 청크 삭제."""
    collection = _get_collection()
    results = collection.get(where={"doc_id": doc_id}, include=[])
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
    return len(ids)
