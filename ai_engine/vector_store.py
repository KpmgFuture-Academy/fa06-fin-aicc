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
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers.ensemble import EnsembleRetriever
from app.core.config import settings


# 전역 변수: 벡터 스토어와 임베딩 모델
_vector_store: Optional[Chroma] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None
_bm25_retriever: Optional[BM25Retriever] = None
_ensemble_retriever: Optional[EnsembleRetriever] = None


def _slugify(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[^0-9A-Za-z_-]+", "-", value.strip()).strip("-")
    return cleaned.lower()


def _filter_complex_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """ChromaDB 호환을 위해 복잡한 메타데이터 타입을 변환합니다.
    
    Args:
        metadata: 원본 메타데이터
        
    Returns:
        변환된 메타데이터 (리스트는 문자열로 변환)
    """
    filtered = {}
    for key, value in metadata.items():
        if isinstance(value, list):
            # 리스트를 쉼표로 구분된 문자열로 변환
            filtered[key] = ", ".join(str(item) for item in value)
        elif isinstance(value, dict):
            # 딕셔너리는 JSON 문자열로 변환
            import json
            filtered[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            # None은 그대로 유지
            filtered[key] = None
        else:
            # 기본 타입 (str, int, float, bool)은 그대로 유지
            filtered[key] = value
    return filtered


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
            model_kwargs={"device": "cpu"},
            encode_kwargs={
                "normalize_embeddings": True,  # 코사인 유사도 최적화
                "batch_size": 32  # 배치 크기 설정 (성능 향상)
            }
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
        
        # ChromaDB는 리스트 타입 메타데이터를 지원하지 않으므로 문자열로 변환
        base_metadata = _filter_complex_metadata(base_metadata)

        for j, chunk in enumerate(chunks):
            metadata = base_metadata.copy()
            metadata["chunk_index"] = j
            chunk_id = _build_chunk_id(metadata, i, j) or str(uuid4())
            documents.append(Document(page_content=chunk, metadata=metadata))
            chunk_ids.append(chunk_id)

    if not documents:
        return []

    # 중복 ID 제거 (동일 ID가 있으면 첫 번째만 유지)
    seen_ids = set()
    unique_documents = []
    unique_chunk_ids = []
    for doc, chunk_id in zip(documents, chunk_ids):
        if chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            unique_documents.append(doc)
            unique_chunk_ids.append(chunk_id)

    # 기존 동일 ID 청크 제거 (재삽입 대비)
    if unique_chunk_ids:
        try:
            vector_store.delete(ids=unique_chunk_ids)
        except Exception:
            pass  # 새 DB에서는 삭제할 문서가 없을 수 있음

    # 벡터 스토어에 추가
    # LangChain Chroma는 PersistentClient를 사용하면 자동으로 persist되므로
    # 별도의 persist() 호출이 필요 없습니다.
    ids = vector_store.add_documents(unique_documents, ids=unique_chunk_ids if unique_chunk_ids else None)
    
    # BM25 Retriever 재인덱싱 필요 (문서 추가 후)
    if settings.enable_hybrid_search:
        _reset_bm25_retriever()
    
    return ids


def search_documents(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.0
) -> List[dict]:
    """벡터 DB에서 유사 문서를 검색합니다 (Hybrid Search 지원).
    
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
    import logging
    import re
    logger = logging.getLogger(__name__)
    
    logger.info(f"[RAG 검색 시작] query='{query}', top_k={top_k}, threshold={score_threshold}")
    
    # 메타 쿼리 필터링: 상담원 연결 요청 등은 RAG 검색 대상이 아님
    # 이런 쿼리는 실제 금융 상품 정보를 요청하는 것이 아니라 시스템 기능을 요청하는 것
    meta_query_keywords = [
        "상담원 연결", "상담사 연결", "상담원 연결해", "상담사 연결해",
        "상담원 연결해줘", "상담사 연결해줘", "상담원 연결해주세요", "상담사 연결해주세요",
        "직원 연결", "직원 연결해", "직원 연결해줘", "직원 연결해주세요",
        "상담원과 통화", "상담사와 통화", "직원과 통화",
        "상담원 필요", "상담사 필요", "직원 필요", "상담원 원해", "상담사 원해"
    ]
    
    meta_query_patterns = [
        r"상담원.*연결", r"상담사.*연결", r"직원.*연결",
        r"상담원.*부르", r"상담사.*부르", r"직원.*부르",
        r"상담원.*필요", r"상담사.*필요", r"직원.*필요",
        r"연결.*상담원", r"연결.*상담사", r"연결.*직원"
    ]
    
    is_meta_query = (
        any(keyword in query for keyword in meta_query_keywords) or
        any(re.search(pattern, query, re.IGNORECASE) for pattern in meta_query_patterns)
    )
    
    if is_meta_query:
        logger.info(f"[1단계: 메타 쿼리 필터링] 메타 쿼리 감지 - RAG 검색 건너뜀: query='{query}'")
        return []  # 빈 결과 반환 (상담원 연결 요청은 RAG 검색 대상이 아님)
    
    # 쿼리 확장 (벡터 + BM25 모두 적용)
    # 구어체 → 문어체 매핑으로 검색 품질 개선
    if settings.enable_query_expansion:
        from ai_engine.utils.query_expansion import expand_query
        expanded_query = expand_query(query)
        vector_search_query = expanded_query  # 벡터 검색에도 확장 쿼리 적용
        bm25_search_query = expanded_query    # BM25 검색에도 확장 쿼리 적용
        if expanded_query != query:
            logger.info(f"[2단계: 쿼리 확장] 원본: '{query}'")
            logger.info(f"[2단계: 쿼리 확장] 확장: '{expanded_query}'")
        else:
            logger.info(f"[2단계: 쿼리 확장] 확장 없음 - 원본 쿼리 사용: '{query}'")
    else:
        vector_search_query = query
        bm25_search_query = query
        logger.info(f"[2단계: 쿼리 확장] 비활성화 - 원본 쿼리 사용: '{query}'")
    
    # Hybrid Search 사용 여부 확인
    if settings.enable_hybrid_search:
        # 자체 RRF 구현 사용 (EnsembleRetriever 대신)
        try:
            vector_store = get_vector_store()
            bm25_retriever = _get_bm25_retriever()
            
            if bm25_retriever is not None:
                # 개선된 방식: 벡터 검색으로 상위 20개 추리고, 그에만 BM25 점수 보정
                # 이렇게 하면 벡터 유사도 점수가 희석되지 않고, BM25가 보정 역할만 수행
                vector_candidate_k = 12  # 벡터 검색으로 상위 12개 추림 (레이턴시 개선)
                
                # 벡터 검색: 원본 쿼리 사용 (임베딩 모델이 의미적 유사도 처리)
                vector_results_with_score = vector_store.similarity_search_with_score(
                    vector_search_query,  # 원본 쿼리
                    k=vector_candidate_k  # 상위 20개만 추림
                )
                
                # 벡터 검색 결과 포맷팅
                vector_results = []
                for doc, score in vector_results_with_score:
                    distance = float(score)
                    # L2 거리를 유사도 점수로 변환 (0~1 범위)
                    # L2 거리는 0~∞ 범위이므로 1/(1+distance) 공식 사용
                    similarity_score = 1.0 / (1.0 + distance)
                    vector_results.append({
                        "content": doc.page_content,
                        "source": doc.metadata.get("source", "unknown"),
                        "page": doc.metadata.get("page", 0),
                        "score": similarity_score
                    })
                
                # 벡터 검색 결과 로깅
                if vector_results:
                    max_vector_score = max(doc['score'] for doc in vector_results)
                    logger.info(f"[3-1단계: 벡터 검색] 상위 {len(vector_results)}개 추림, 최고 점수: {max_vector_score:.4f}")
                else:
                    logger.warning(f"[3-1단계: 벡터 검색] 결과 없음")
                    # 벡터 검색 결과가 없으면 BM25 검색도 의미 없음
                    return []
                
                # 벡터 검색으로 추린 상위 20개 문서에 대해서만 BM25 점수 계산 (보정용)
                # BM25는 독립 검색이 아니라 벡터 결과에 대한 보정만 수행
                vector_doc_list = [Document(page_content=doc["content"], metadata={"source": doc["source"], "page": doc["page"]}) 
                                  for doc in vector_results]
                bm25_scores_dict = _get_bm25_scores(bm25_search_query, vector_doc_list)  # 확장 쿼리로 점수 계산
                
                logger.info(f"[3-2단계: BM25 보정] 벡터 상위 {len(vector_results)}개 문서에 대해 BM25 점수 계산 (보정용)")
                
                # 벡터 점수를 주 점수로 사용, BM25는 보정만 수행
                # 벡터 유사도 점수가 희석되지 않도록 보정 방식 적용
                logger.info(f"[4단계: Hybrid Search 결합] 벡터 주 점수 + BM25 보정 방식 사용")
                
                combined_scores = []
                for vector_doc in vector_results:
                    content = vector_doc["content"]
                    vector_score = vector_doc["score"]
                    
                    # BM25 점수 찾기 (벡터 상위 20개에 대해서만 계산됨)
                    bm25_score = bm25_scores_dict.get(content, 0.0)
                    
                    # 벡터 점수를 주 점수로 사용, BM25는 보정만
                    if vector_score > 0:
                        # BM25 점수가 높으면 약간 보정 (최대 5% 증가)
                        # BM25 점수가 낮으면 보정 없음 (점수 하락 방지)
                        bm25_boost = max(0, (bm25_score - 0.5) * 0.1)  # BM25 > 0.5일 때만 보정
                        final_score = min(vector_score + bm25_boost, 1.0)
                    else:
                        # 벡터 점수가 없으면 BM25 점수 사용 (fallback)
                        final_score = bm25_score
                    
                    combined_scores.append({
                        "content": content,
                        "source": vector_doc["source"],
                        "page": vector_doc["page"],
                        "score": round(final_score, 4)
                    })
                
                # 벡터 점수 순으로 정렬 (BM25 보정 후에도 벡터 점수가 주가 되므로)
                combined_results = sorted(combined_scores, key=lambda x: x["score"], reverse=True)
                
                # score_threshold 적용 (threshold를 넘지 못하면 빈 결과 반환)
                filtered_results = [
                    result for result in combined_results
                    if result["score"] >= score_threshold
                ]
                
                # 결합 후 결과 로깅
                if combined_results:
                    max_score = combined_results[0]['score']
                    logger.info(f"[4단계: Hybrid Search 결합 완료] 총 {len(combined_results)}개 문서, 최고 점수: {max_score:.4f}")
                    # 상위 3개 점수 로깅
                    top_3_scores = [f"{doc['score']:.4f}" for doc in combined_results[:3]]
                    logger.info(f"[4단계: Hybrid Search] 상위 3개 점수: {', '.join(top_3_scores)}")
                
                # threshold를 넘지 못하면 빈 결과 반환 (상담원 이관)
                if len(filtered_results) == 0:
                    max_score = combined_results[0]['score'] if combined_results else 0.0
                    logger.warning(f"[5단계: Threshold 체크] 실패 - 최고 점수 {max_score:.4f} < threshold {score_threshold} → 빈 결과 반환 (상담원 이관)")
                    return []
                else:
                    max_score = filtered_results[0]['score']
                    logger.info(f"[5단계: Threshold 체크] 통과 - 최고 점수 {max_score:.4f} >= threshold {score_threshold}, {len(filtered_results)}개 문서 통과")
                
                # threshold를 넘은 경우에만 Reranking 적용 (rerank_score 반영)
                if settings.enable_reranking and len(filtered_results) > 0:
                    rerank_candidates = filtered_results[:settings.rerank_top_k]
                    logger.info(f"[6단계: Reranking] 시작 - 상위 {len(rerank_candidates)}개 문서 재정렬 (모델: {settings.reranker_model})")

                    # 원본 점수 저장 (로깅용)
                    original_scores = {doc["content"]: doc["score"] for doc in rerank_candidates}

                    reranked_results = _rerank_documents(
                        query=query,  # 원본 쿼리 사용
                        documents=rerank_candidates,
                        top_k=settings.rerank_final_k,
                        return_raw_scores=True  # rerank_score 반환
                    )

                    # rerank_score를 score로 사용 (원본 점수는 original_score로 보관)
                    for result in reranked_results:
                        content = result["content"]
                        original_score = original_scores.get(content, 0.0)
                        result["original_score"] = round(original_score, 4)  # 로깅용 원본 점수
                        # rerank_score를 score로 사용 (RAG Score 평가에 반영)
                        if "rerank_score" in result:
                            result["score"] = result["rerank_score"]

                    formatted_results = reranked_results
                    logger.info(f"[6단계: Reranking] 완료 - 최종 {len(formatted_results)}개 문서 반환 (rerank_score 반영)")
                    # 최종 상위 3개 점수 로깅 (rerank_score 기준)
                    top_3_final = [f"{doc['score']:.4f}" for doc in formatted_results[:3]]
                    top_3_original = [f"{doc.get('original_score', 0):.4f}" for doc in formatted_results[:3]]
                    logger.info(f"[6단계: Reranking] 최종 상위 3개 rerank_score: {', '.join(top_3_final)} (원본: {', '.join(top_3_original)})")
                else:
                    # Reranking 비활성화 시 top_k만큼만 반환
                    formatted_results = filtered_results[:top_k]
                    logger.info(f"[6단계: Reranking] 비활성화 - 상위 {len(formatted_results)}개 문서 반환")

                # [7단계: 동적 검색 건수 조정] RAG Score 높으면 1건만 사용하여 LLM 컨텍스트 최소화
                if formatted_results and formatted_results[0]['score'] >= 0.70:
                    # 최고 점수가 0.70 이상이면 1건만 반환 (충분히 관련성 높음)
                    formatted_results = formatted_results[:1]
                    logger.info(f"[7단계: 동적 조정] 최고 점수 {formatted_results[0]['score']:.4f} >= 0.70 → 1건만 반환 (레이턴시 최적화)")
                elif formatted_results and formatted_results[0]['score'] >= 0.60:
                    # 0.60~0.70 사이면 2건 반환
                    formatted_results = formatted_results[:2]
                    logger.info(f"[7단계: 동적 조정] 최고 점수 >= 0.60 → 2건 반환")
                else:
                    # 0.60 미만이면 기존대로 3건 반환
                    logger.info(f"[7단계: 동적 조정] 최고 점수 < 0.60 → 3건 유지")
                
                logger.info(f"[RAG 검색 완료] Hybrid Search (벡터 주 점수 + BM25 보정) + Reranking: query='{query}', 최종 결과 {len(formatted_results)}개 문서")
                return formatted_results
            else:
                logger.warning("BM25Retriever를 사용할 수 없어 벡터 검색만 사용합니다.")
        except Exception as e:
            logger.warning(f"Hybrid Search 실패, 벡터 검색으로 fallback: {e}", exc_info=True)
    
    # 벡터 검색만 사용 (Hybrid Search 비활성화 또는 실패 시)
    logger.info(f"[Fallback: 벡터 검색만 사용] Hybrid Search 비활성화 또는 실패")
    vector_store = get_vector_store()
    
    # 유사도 검색 수행 (Reranking을 위해 더 많이 가져오기)
    # 벡터 검색은 항상 원본 쿼리 사용 (임베딩 모델이 의미적 유사도 처리)
    search_k = settings.rerank_top_k if settings.enable_reranking else top_k
    logger.info(f"[Fallback: 벡터 검색] 시작 - search_k={search_k}, 원본 쿼리 사용")
    results = vector_store.similarity_search_with_score(
        query,  # 원본 쿼리 사용
        k=search_k
    )
    
    # 결과 포맷팅
    formatted_results = []
    for doc, score in results:
        # ChromaDB는 L2 거리(distance)를 반환합니다
        distance = float(score)

        # L2 거리를 유사도 점수로 변환 (0~1 범위)
        # L2 거리는 0~∞ 범위이므로 1/(1+distance) 공식 사용
        similarity_score = 1.0 / (1.0 + distance)
        
        formatted_results.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source", "unknown"),
            "page": doc.metadata.get("page", 0),
            "score": round(similarity_score, 4)
        })
    
    if formatted_results:
        max_score = max(doc['score'] for doc in formatted_results)
        logger.info(f"[Fallback: 벡터 검색] 결과: {len(formatted_results)}개, 최고 점수: {max_score:.4f}")
    
    # score_threshold 적용 (threshold를 넘지 못하면 빈 결과 반환)
    filtered_results = [
        result for result in formatted_results
        if result["score"] >= score_threshold
    ]
    
    # threshold를 넘지 못하면 빈 결과 반환 (상담원 이관)
    if len(filtered_results) == 0:
        max_score = formatted_results[0]['score'] if formatted_results else 0.0
        logger.warning(f"[Fallback: Threshold 체크] 실패 - 최고 점수 {max_score:.4f} < threshold {score_threshold} → 빈 결과 반환 (상담원 이관)")
        return []
    else:
        max_score = filtered_results[0]['score']
        logger.info(f"[Fallback: Threshold 체크] 통과 - 최고 점수 {max_score:.4f} >= threshold {score_threshold}, {len(filtered_results)}개 문서 통과")
    
    # threshold를 넘은 경우에만 Reranking 적용 (rerank_score 반영)
    if settings.enable_reranking and len(filtered_results) > 0:
        rerank_candidates = filtered_results[:settings.rerank_top_k]

        # 원본 점수 저장 (로깅용)
        original_scores = {doc["content"]: doc["score"] for doc in rerank_candidates}

        reranked_results = _rerank_documents(
            query=query,  # 원본 쿼리 사용
            documents=rerank_candidates,
            top_k=settings.rerank_final_k,
            return_raw_scores=True  # rerank_score 반환
        )

        # rerank_score를 score로 사용 (원본 점수는 original_score로 보관)
        for result in reranked_results:
            content = result["content"]
            original_score = original_scores.get(content, 0.0)
            result["original_score"] = round(original_score, 4)  # 로깅용 원본 점수
            # rerank_score를 score로 사용 (RAG Score 평가에 반영)
            if "rerank_score" in result:
                result["score"] = result["rerank_score"]

        formatted_results = reranked_results
    else:
        # Reranking 비활성화 시 top_k만큼만 반환
        formatted_results = filtered_results[:top_k]

    # [Fallback 동적 조정] RAG Score 높으면 1건만 사용
    if formatted_results and formatted_results[0]['score'] >= 0.70:
        formatted_results = formatted_results[:1]
    elif formatted_results and formatted_results[0]['score'] >= 0.60:
        formatted_results = formatted_results[:2]

    return formatted_results


def reset_vector_store():
    """벡터 스토어를 초기화합니다 (모든 문서 삭제 및 컬렉션 재생성)."""
    global _vector_store
    
    # 벡터 스토어 초기화
    _vector_store = None
    
    # ChromaDB 디렉토리 삭제 (완전 초기화)
    import shutil
    db_path = Path(settings.vector_db_path)
    if db_path.exists():
        try:
            # 파일이 열려있을 수 있으므로 여러 번 시도
            import time
            for _ in range(3):
                try:
                    shutil.rmtree(db_path)
                    break
                except PermissionError:
                    time.sleep(0.5)
                    continue
        except Exception as e:
            print(f"[WARNING] 벡터 DB 디렉토리 삭제 실패: {e}")
            # 수동으로 삭제하도록 안내
            print(f"[INFO] 수동으로 {db_path} 디렉토리를 삭제한 후 다시 시도하세요.")
    
    # 새로 생성
    get_vector_store()
    
    # BM25 Retriever도 초기화
    _reset_bm25_retriever()


def _get_all_documents() -> List[Document]:
    """벡터 스토어에서 모든 문서를 가져옵니다 (BM25 인덱싱용).
    
    Returns:
        모든 Document 리스트
    """
    vector_store = get_vector_store()
    # ChromaDB에서 모든 문서 가져오기
    # k를 충분히 크게 설정하여 모든 문서 가져오기
    all_docs = vector_store.similarity_search("", k=10000)  # 충분히 큰 값
    return all_docs


def _get_bm25_retriever() -> Optional[BM25Retriever]:
    """BM25 Retriever를 생성하고 반환합니다 (싱글톤 패턴).
    
    Returns:
        BM25Retriever 인스턴스 (문서가 없으면 None)
    """
    global _bm25_retriever
    
    if _bm25_retriever is None:
        try:
            # 모든 문서 가져오기
            documents = _get_all_documents()
            
            if not documents:
                return None
            
            # BM25Retriever 생성 (한국어 토크나이저 적용)
            # preprocess_func을 사용하여 한국어 토크나이저 적용
            _bm25_retriever = BM25Retriever.from_documents(
                documents,
                preprocess_func=_tokenize_korean  # 한국어 토크나이저 사용
            )
            _bm25_retriever.k = 5  # 기본 검색 개수
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"BM25Retriever 생성 실패: {e}. 벡터 검색만 사용합니다.")
            return None
    
    return _bm25_retriever


def _tokenize_korean(text: str) -> List[str]:
    """한국어 텍스트를 토큰화합니다.
    
    Args:
        text: 토큰화할 텍스트
        
    Returns:
        토큰 리스트
    """
    import re
    
    # 설정에서 한국어 토크나이저 확인
    tokenizer_type = settings.bm25_korean_tokenizer
    
    # Kiwi 형태소 분석기 사용
    if tokenizer_type == "kiwi":
        try:
            # Kiwi 인스턴스 생성 (싱글톤 패턴)
            if not hasattr(_tokenize_korean, '_kiwi'):
                from kiwipiepy import Kiwi
                _tokenize_korean._kiwi = Kiwi()
                
                # 금융 용어 사용자 사전 추가
                # 1. 기본 금융 용어
                basic_financial_terms = [
                    "카드론", "현금서비스", "주담대", "전세자금대출",
                    "신용대출", "담보대출", "마이너스통장", "적금",
                    "예금", "정기예금", "정기적금", "자유적금",
                    "주택담보대출", "전세보증금", "신용카드", "체크카드",
                    "KB국민은행", "KB카드", "KB증권", "KB생명"
                ]
                
                # 2. JSON 파일에서 intents 추출하여 추가
                try:
                    import json
                    json_path = Path(__file__).parent.parent.parent / "data" / "kb_finance_insurance_60items_v1.json"
                    if json_path.exists():
                        with open(json_path, 'r', encoding='utf-8') as f:
                            kb_data = json.load(f)
                        
                        # 모든 intents 추출 (# 제거)
                        intents_from_json = set()
                        for item in kb_data:
                            for intent in item.get('intents', []):
                                intent_clean = intent.replace('#', '').strip()
                                if intent_clean:
                                    intents_from_json.add(intent_clean)
                        
                        # 기본 용어와 합치기
                        all_terms = set(basic_financial_terms) | intents_from_json
                    else:
                        all_terms = set(basic_financial_terms)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"JSON 파일에서 intents 로드 실패: {e}. 기본 용어만 사용합니다.")
                    all_terms = set(basic_financial_terms)
                
                # 사용자 사전에 추가
                for term in all_terms:
                    try:
                        _tokenize_korean._kiwi.add_user_word(term, tag='NNP')  # 고유명사
                    except Exception:
                        pass  # 이미 추가된 단어는 무시
            
            kiwi = _tokenize_korean._kiwi
            
            # 형태소 분석 수행
            # analyze()는 (Token 리스트, 점수) 튜플을 반환
            # Token 객체: form(형태소), tag(품사), start(시작위치), len(길이)
            tokens = []
            morphs_result = kiwi.analyze(text)
            
            # 첫 번째 결과만 사용 (가장 높은 점수)
            if morphs_result and len(morphs_result) > 0:
                morphs = morphs_result[0]  # Token 리스트
                
                for token in morphs:
                    # Token 객체인 경우
                    if hasattr(token, 'form') and hasattr(token, 'tag'):
                        word = token.form  # 형태소
                        pos = token.tag    # 한국어 품사 태그
                    # 튜플인 경우 (구버전 호환)
                    elif isinstance(token, (list, tuple)) and len(token) >= 2:
                        word = token[0]
                        pos = token[1]
                    else:
                        continue
                    
                    # 한국어 품사 태그 체계 (세종 품사 태그 기준)
                    # N: 명사 (NNG: 일반명사, NNP: 고유명사, NNB: 의존명사 등)
                    # V: 동사 (VV: 동사, VA: 형용사)
                    # A: 형용사 (VA로 처리됨)
                    # M: 부사 (MA: 부사)
                    # SL: 외국어, SN: 숫자
                    # 불필요한 품사 제외: J(조사), E(어미), X(접사), S(기호) 등
                    if pos:
                        pos_first = pos[0] if len(pos) > 0 else ''
                        # 명사, 동사, 형용사, 부사, 외국어, 숫자만 추출
                        if pos_first in ['N', 'V', 'A', 'M'] or pos in ['SL', 'SN']:
                            token_str = word.strip()
                            if len(token_str) > 0:
                                tokens.append(token_str.lower())
            
            # 영문과 숫자도 추가 (형태소 분석에서 놓친 경우)
            tokens.extend(re.findall(r'[a-zA-Z]+|\d+', text.lower()))
            
            # 중복 제거 및 빈 토큰 제거
            tokens = list(dict.fromkeys([t for t in tokens if len(t) > 0]))
            
            return tokens if tokens else [text.lower()]  # 토큰이 없으면 원본 반환
            
        except ImportError:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("kiwipiepy가 설치되지 않았습니다. 기본 토크나이저를 사용합니다.")
            # Fallback to default
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Kiwi 형태소 분석 실패: {e}. 기본 토크나이저를 사용합니다.")
            # Fallback to default
    
    # 기본 토크나이저: 공백 + 한글 단어 추출
    # 한글, 영문, 숫자를 포함한 단어 추출
    tokens = re.findall(r'[가-힣]+|[a-zA-Z]+|\d+', text.lower())
    return tokens


def _rrf_combine_results(
    vector_results: List[dict],
    bm25_results: List[dict],
    k: int = 60
) -> List[dict]:
    """RRF (Reciprocal Rank Fusion)를 사용하여 벡터 검색과 BM25 검색 결과를 결합합니다.
    
    Args:
        vector_results: 벡터 검색 결과 리스트 (각 항목은 content, source, page, score 포함)
        bm25_results: BM25 검색 결과 리스트 (각 항목은 content, source, page 포함)
        k: RRF 상수 (일반적으로 60 사용, 낮을수록 순위 영향 큼)
        
    Returns:
        RRF 점수로 결합된 결과 리스트 (점수 순으로 정렬됨)
    """
    # 문서별 RRF 점수 계산
    rrf_scores = {}  # content -> {"score": float, "metadata": dict}
    
    # 벡터 검색 순위 점수 추가
    for rank, doc in enumerate(vector_results, start=1):
        content = doc["content"]
        rrf_score = 1.0 / (k + rank)
        
        if content not in rrf_scores:
            rrf_scores[content] = {
                "score": 0.0,
                "source": doc.get("source", "unknown"),
                "page": doc.get("page", 0)
            }
        rrf_scores[content]["score"] += rrf_score
    
    # BM25 검색 순위 점수 추가
    for rank, doc in enumerate(bm25_results, start=1):
        content = doc["content"]
        rrf_score = 1.0 / (k + rank)
        
        if content not in rrf_scores:
            rrf_scores[content] = {
                "score": 0.0,
                "source": doc.get("source", "unknown"),
                "page": doc.get("page", 0)
            }
        rrf_scores[content]["score"] += rrf_score
    
    # RRF 점수 순으로 정렬
    sorted_items = sorted(
        rrf_scores.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )
    
    # RRF 점수를 0-1 범위로 정규화 (Min-Max 정규화)
    if sorted_items:
        scores = [item[1]["score"] for item in sorted_items]
        max_score = max(scores)
        min_score = min(scores)
        
        if max_score > min_score:
            # Min-Max 정규화
            normalized_results = [
                {
                    "content": content,
                    "source": data["source"],
                    "page": data["page"],
                    "score": round((data["score"] - min_score) / (max_score - min_score), 4)
                }
                for content, data in sorted_items
            ]
        else:
            # 모든 점수가 같으면 1.0으로 설정
            normalized_results = [
                {
                    "content": content,
                    "source": data["source"],
                    "page": data["page"],
                    "score": 1.0 if max_score > 0 else 0.0
                }
                for content, data in sorted_items
            ]
    else:
        normalized_results = []
    
    return normalized_results


def _get_bm25_scores(query: str, documents: List[Document]) -> Dict[str, float]:
    """BM25 점수를 계산하여 반환합니다.
    
    Args:
        query: 검색 쿼리
        documents: 점수를 계산할 문서 리스트
        
    Returns:
        문서 content를 키로 하고 BM25 점수를 값으로 하는 딕셔너리 (0-1 정규화)
    """
    bm25_retriever = _get_bm25_retriever()
    if bm25_retriever is None or not documents:
        return {}
    
    try:
        # rank_bm25를 직접 사용하여 점수 계산
        from rank_bm25 import BM25Okapi
        import re
        
        # 쿼리 토큰화 (한국어 최적화)
        query_tokens = _tokenize_korean(query)
        if not query_tokens:
            return {}
        
        # 모든 문서 가져오기 (BM25 인덱스 구축용)
        all_docs = _get_all_documents()
        
        # 문서들을 토큰화 (한국어 최적화)
        tokenized_docs = []
        for doc in all_docs:
            tokens = _tokenize_korean(doc.page_content)
            tokenized_docs.append(tokens)
        
        # BM25 인덱스 생성
        bm25 = BM25Okapi(tokenized_docs)
        
        # 쿼리에 대한 모든 문서의 BM25 점수 계산
        all_scores = bm25.get_scores(query_tokens)
        
        # 요청된 문서들의 점수만 추출
        doc_content_to_index = {doc.page_content: i for i, doc in enumerate(all_docs)}
        scores = {}
        
        for doc in documents:
            content = doc.page_content
            doc_index = doc_content_to_index.get(content)
            
            if doc_index is not None and doc_index < len(all_scores):
                score = float(all_scores[doc_index])
                scores[content] = score
            else:
                scores[content] = 0.0
        
        # 점수 정규화 (0-1 범위로 변환)
        if scores:
            max_score = max(scores.values())
            min_score = min(scores.values())
            if max_score > min_score:
                # Min-Max 정규화
                scores = {k: (v - min_score) / (max_score - min_score) for k, v in scores.items()}
            elif max_score > 0:
                # 모든 점수가 같고 0이 아닌 경우
                scores = {k: 1.0 for k in scores.keys()}
            else:
                # 모든 점수가 0인 경우
                scores = {k: 0.0 for k in scores.keys()}
        
        return scores
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"BM25 점수 계산 실패: {e}", exc_info=True)
        # Fallback: 간단한 키워드 매칭 (Jaccard 유사도)
        query_tokens = set(_tokenize_korean(query))
        scores = {}
        for doc in documents:
            content = doc.page_content
            doc_tokens = set(_tokenize_korean(content))
            intersection = len(query_tokens & doc_tokens)
            union = len(query_tokens | doc_tokens)
            score = intersection / union if union > 0 else 0.0
            scores[content] = float(score)
        return scores


def _rerank_documents(
    query: str,
    documents: List[dict],
    top_k: int = 5,
    return_raw_scores: bool = False
) -> List[dict]:
    """Cross-Encoder를 사용하여 검색 결과를 재정렬합니다.
    
    Args:
        query: 검색 쿼리
        documents: 재정렬할 문서 리스트 (각 항목은 content, source, page, score 포함)
        top_k: 최종 반환할 문서 수
        return_raw_scores: True면 원본 Reranking 점수도 반환 (rerank_score 필드에 저장)
        
    Returns:
        재정렬된 문서 리스트
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not documents or not settings.enable_reranking:
        return documents[:top_k]
    
    try:
        from sentence_transformers import CrossEncoder
        
        # Cross-Encoder 모델 로드 (싱글톤)
        if not hasattr(_rerank_documents, '_model'):
            logger.info(f"[Reranking 내부] 모델 로드 중: {settings.reranker_model}")
            _rerank_documents._model = CrossEncoder(settings.reranker_model)
            logger.info(f"[Reranking 내부] 모델 로드 완료")
        
        model = _rerank_documents._model
        
        # 쿼리-문서 쌍 생성
        pairs = [[query, doc["content"]] for doc in documents]
        logger.debug(f"[Reranking 내부] {len(pairs)}개 쿼리-문서 쌍 생성")
        
        # 점수 계산 (원본 점수)
        # show_progress_bar=False로 설정하여 tqdm hang 방지
        raw_scores = model.predict(pairs, show_progress_bar=False)
        scores_array = [float(score) for score in raw_scores]
        
        if scores_array:
            min_score = min(scores_array)
            max_score = max(scores_array)
            logger.debug(f"[Reranking 내부] Cross-Encoder 점수 범위: {min_score:.4f} ~ {max_score:.4f}")
        
        # 점수와 문서 결합
        if return_raw_scores:
            # 원본 점수 반환 (정규화하지 않음)
            scored_docs = [
                {**doc, "rerank_score": round(score, 4)}
                for doc, score in zip(documents, scores_array)
            ]
        else:
            # 기존 방식: Min-Max 정규화 (하위 호환성)
            if scores_array:
                max_score = max(scores_array)
                min_score = min(scores_array)
                
                if max_score > min_score:
                    # Min-Max 정규화 (0-1 범위)
                    normalized_scores = [
                        (score - min_score) / (max_score - min_score)
                        for score in scores_array
                    ]
                else:
                    # 모든 점수가 같으면 1.0으로 설정
                    normalized_scores = [1.0 if max_score > 0 else 0.0] * len(scores_array)
            else:
                normalized_scores = scores_array
            
            scored_docs = [
                {**doc, "score": round(score, 4)}
                for doc, score in zip(documents, normalized_scores)
            ]
        
        # 점수 순으로 정렬 (rerank_score 또는 score 기준)
        sort_key = "rerank_score" if return_raw_scores else "score"
        scored_docs.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
        
        # 정렬 후 상위 점수 로깅
        if scored_docs:
            top_scores = [f"{doc.get(sort_key, 0):.4f}" for doc in scored_docs[:3]]
            logger.debug(f"[Reranking 내부] 정렬 후 상위 3개 점수: {', '.join(top_scores)}")
        
        # top_k만큼 반환
        return scored_docs[:top_k]
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Reranking 실패, 원본 순서 유지: {e}", exc_info=True)
        # Fallback: 원본 순서 유지
        return documents[:top_k]


def _reset_bm25_retriever():
    """BM25 Retriever를 초기화합니다 (문서 추가/삭제 후 재인덱싱 필요)."""
    global _bm25_retriever
    _bm25_retriever = None


def get_retriever(k: int = 5, score_threshold: float = 0.0):
    """LangChain Retriever를 반환합니다 (Hybrid Search 지원).
    
    참고: 현재는 자체 RRF 구현을 사용하므로 이 함수는 주로 호환성을 위해 유지됩니다.
    실제 Hybrid Search는 search_documents() 함수에서 직접 구현된 RRF를 사용합니다.
    
    Args:
        k: 반환할 최대 문서 수
        score_threshold: 최소 유사도 점수
        
    Returns:
        LangChain Retriever 인스턴스 (Hybrid Search 활성화 시 EnsembleRetriever, 
        하지만 실제로는 사용되지 않음)
    """
    vector_store = get_vector_store()
    
    # Hybrid Search 활성화 여부 확인
    if settings.enable_hybrid_search:
        # BM25 Retriever 가져오기
        bm25_retriever = _get_bm25_retriever()
        
        if bm25_retriever is not None:
            # 벡터 Retriever 생성
            vector_retriever = vector_store.as_retriever(
                search_kwargs={
                    "k": k,
                    "score_threshold": score_threshold
                }
            )
            
            # BM25 Retriever 설정
            bm25_retriever.k = k
            
            # EnsembleRetriever 생성 (가중치 결합)
            ensemble_retriever = EnsembleRetriever(
                retrievers=[vector_retriever, bm25_retriever],
                weights=[settings.vector_search_weight, settings.bm25_search_weight]
            )
            
            return ensemble_retriever
        else:
            # BM25 생성 실패 시 벡터 검색만 사용
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("BM25Retriever를 사용할 수 없어 벡터 검색만 사용합니다.")
    
    # Hybrid Search 비활성화 또는 BM25 실패 시 벡터 검색만 사용
    retriever = vector_store.as_retriever(
        search_kwargs={
            "k": k,
            "score_threshold": score_threshold
        }
    )
    
    return retriever

