"""
ChromaDB 벡터 스토어.
- 임베딩: intfloat/multilingual-e5-large (한국어+영어 최적)
- 쿼리 시 "query: " 접두사 필수 (e5 모델 스펙)
- 컬렉션: telecom_docs
"""
from __future__ import annotations

import os

from app.config import settings
from app.modules.chunker import IndexChunk

COLLECTION_NAME = "telecom_docs"

# 싱글톤 — 첫 검색 요청 시 초기화 (lazy)
_chroma_client = None
_collection = None


def _get_collection():
    import chromadb  # noqa: PLC0415
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2  # noqa: PLC0415

    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
    if _collection is None:
        ef = ONNXMiniLM_L6_V2()  # chromadb 번들 모델 — 별도 다운로드 없음
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
