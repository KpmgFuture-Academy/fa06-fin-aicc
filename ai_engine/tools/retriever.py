# ai_engine/tools/retriever.py
# 벡터 DB 검색 도구 - RAG 검색 로직

"""벡터 DB에서 유사 문서를 검색하는 도구
이 모듈은 순수한 검색 로직만 담당하며, LangGraph와 독립적으로 사용 가능하다.
"""

from typing import List

from ai_engine.graph.state import RetrievedDocument


def search_documents(query: str, top_k: int = 5) -> List[RetrievedDocument]:
    """사용자 질문과 유사한 문서를 벡터 DB에서 검색.

    Args:
        query: 사용자 질문
        top_k: 반환할 문서 개수 (기본값: 5)

    Returns:
        검색된 문서 리스트 (유사도 높은 순서)

    TODO:
        - 벡터 DB 연결 설정 (ChromaDB, FAISS, Pinecone 등)
        - 임베딩 모델 설정 (sentence-transformers 등)
        - 실제 검색 로직 구현
    """
    # TODO: 벡터 DB 연결 및 검색 로직 구현
    # 예시 구조:
    # 1. query를 임베딩으로 변환
    # 2. 벡터 DB에서 유사도 검색
    # 3. 결과를 RetrievedDocument 형태로 변환
    raise NotImplementedError("search_documents() is not implemented yet.")

# query를 벡터 임베딩으로 변환
def embed_query(query: str) -> List[float]:
    """질문을 벡터 임베딩으로 변환.

    Args:
        query: 사용자 질문

    Returns:
        임베딩 벡터 (리스트)

    TODO:
        - 임베딩 모델 로드 및 사용
        - sentence-transformers 또는 OpenAI embeddings 사용
    """
    # TODO: 임베딩 모델 구현
    raise NotImplementedError("embed_query() is not implemented yet.")
