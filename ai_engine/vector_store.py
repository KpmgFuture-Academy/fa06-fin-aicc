"""벡터 DB 초기화 및 관리 모듈
ChromaDB를 사용하여 문서 임베딩 및 검색을 관리합니다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.core.config import settings


# 전역 변수: 벡터 스토어와 임베딩 모델
_vector_store: Optional[Chroma] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None


def _slugify(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[^0-9A-Za-z_-]+", "-", value.strip()).strip("-")
    return cleaned.lower()


def _build_chunk_id(metadata: Dict[str, Any], document_index: int, chunk_index: int) -> str:
    kb_id = metadata.get("kb_id")
    base = _slugify(str(kb_id)) if kb_id not in (None, "") else ""
    if not base:
        base = (
            _slugify(metadata.get("title"))
            or _slugify(metadata.get("source"))
            or f"doc-{document_index}"
        )
    if not base:
        base = f"doc-{document_index}"
    return f"{base}-chunk-{chunk_index}"


def get_embeddings() -> HuggingFaceEmbeddings:
    """임베딩 모델 인스턴스를 반환합니다 (싱글톤 패턴).
    
    Returns:
        HuggingFaceEmbeddings 인스턴스
    """
    global _embeddings
    
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},  # GPU 사용 시 "cuda"로 변경
            encode_kwargs={"normalize_embeddings": True}  # 코사인 유사도 최적화
        )
    
    return _embeddings


def get_vector_store() -> Chroma:
    """벡터 스토어 인스턴스를 반환합니다 (싱글톤 패턴).
    
    Returns:
        Chroma 벡터 스토어 인스턴스
    """
    global _vector_store
    
    if _vector_store is None:
        # ChromaDB 저장 경로 생성
        db_path = Path(settings.vector_db_path)
        db_path.mkdir(parents=True, exist_ok=True)
        
        # ChromaDB 클라이언트 생성
        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # LangChain Chroma 벡터 스토어 생성
        _vector_store = Chroma(
            client=client,
            collection_name=settings.collection_name,
            embedding_function=get_embeddings(),
            persist_directory=str(db_path)
        )
    
    return _vector_store


def add_documents(
    texts: List[str],
    metadatas: Optional[List[dict]] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[str]:
    """문서를 벡터 DB에 추가합니다.
    
    Args:
        texts: 추가할 텍스트 리스트
        metadatas: 각 텍스트의 메타데이터 리스트 (source, page 등)
        chunk_size: 텍스트 분할 크기
        chunk_overlap: 텍스트 분할 시 겹치는 문자 수
        
    Returns:
        추가된 문서 ID 리스트
    """
    vector_store = get_vector_store()
    
    # 텍스트 분할기 생성
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", "。", ".", " ", ""]
    )
    
    # 문서 생성
    documents: List[Document] = []
    chunk_ids: List[str] = []
    for i, text in enumerate(texts):
        chunks = text_splitter.split_text(text)
        base_metadata = metadatas[i].copy() if metadatas and i < len(metadatas) else {}
        base_metadata.setdefault("document_index", i)

        for j, chunk in enumerate(chunks):
            metadata = base_metadata.copy()
            metadata["chunk_index"] = j
            chunk_id = _build_chunk_id(metadata, i, j) or str(uuid4())
            documents.append(Document(page_content=chunk, metadata=metadata))
            chunk_ids.append(chunk_id)

    if not documents:
        return []

    # 기존 동일 ID 청크 제거 (재삽입 대비)
    if chunk_ids:
        vector_store.delete(ids=chunk_ids)

    # 벡터 스토어에 추가
    ids = vector_store.add_documents(documents, ids=chunk_ids if chunk_ids else None)
    vector_store.persist()
    
    return ids


def search_documents(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.0
) -> List[dict]:
    """벡터 DB에서 유사 문서를 검색합니다.
    
    Args:
        query: 검색 쿼리
        top_k: 반환할 최대 문서 수
        score_threshold: 최소 유사도 점수 (0.0 ~ 1.0)
        
    Returns:
        검색 결과 리스트. 각 항목은 다음 키를 포함:
        - content: 문서 내용
        - source: 출처 파일명
        - page: 페이지 번호
        - score: 유사도 점수
    """
    vector_store = get_vector_store()
    
    # 유사도 검색 수행
    results = vector_store.similarity_search_with_score(
        query,
        k=top_k
    )
    
    # 결과 포맷팅
    formatted_results = []
    for doc, score in results:
        # ChromaDB는 거리 기반 점수를 반환하므로 유사도로 변환
        # 거리가 작을수록 유사도가 높음 (0에 가까울수록 유사)
        # 코사인 유사도로 변환: similarity = 1 - distance (정규화된 경우)
        similarity_score = max(0.0, 1.0 - float(score))
        
        if similarity_score >= score_threshold:
            formatted_results.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "page": doc.metadata.get("page", 0),
                "score": round(similarity_score, 4)
            })
    
    return formatted_results


def reset_vector_store():
    """벡터 스토어를 초기화합니다 (모든 문서 삭제)."""
    global _vector_store
    
    if _vector_store is not None:
        # 컬렉션 삭제
        _vector_store.delete_collection()
        _vector_store = None
    
    # 새로 생성
    get_vector_store()


def get_retriever(k: int = 5, score_threshold: float = 0.0):
    """LangChain Retriever를 반환합니다.
    
    Args:
        k: 반환할 최대 문서 수
        score_threshold: 최소 유사도 점수
        
    Returns:
        LangChain Retriever 인스턴스
    """
    vector_store = get_vector_store()
    
    # Retriever 생성 (필터링 옵션 포함 가능)
    retriever = vector_store.as_retriever(
        search_kwargs={
            "k": k,
            "score_threshold": score_threshold
        }
    )
    
    return retriever

