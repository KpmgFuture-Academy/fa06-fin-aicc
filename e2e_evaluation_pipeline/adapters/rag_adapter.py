# e2e_evaluation_pipeline/adapters/rag_adapter.py
"""RAG 검색 모듈과 E2E 평가 파이프라인 연동 어댑터.

실제 ChromaDB 벡터 스토어를 호출하여 RAG 검색 결과를
평가 가능한 형태로 변환합니다.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RetrievedDocument:
    """검색된 문서"""
    content: str
    source: str
    page: int = 0
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGSearchResult:
    """RAG 검색 결과"""
    query: str
    documents: List[RetrievedDocument]
    best_score: float = 0.0
    is_confident: bool = True
    error: Optional[str] = None


# 신뢰도 임계값
LOW_CONFIDENCE_THRESHOLD = 0.5
HIGH_CONFIDENCE_THRESHOLD = 0.7


class RAGAdapter:
    """RAG 검색 어댑터.

    E2E 평가 파이프라인에서 실제 ChromaDB 벡터 스토어를 호출하고
    결과를 평가 가능한 형태로 변환합니다.
    """

    def __init__(self, score_threshold: float = 0.3):
        """
        Args:
            score_threshold: 최소 점수 임계값
        """
        self._search_func = None
        self._initialized = False
        self.score_threshold = score_threshold

    def _ensure_initialized(self):
        """검색 함수 지연 초기화"""
        if self._initialized:
            return

        try:
            from ai_engine.vector_store import search_documents
            self._search_func = search_documents
            self._initialized = True
            logger.info("RAG 검색 모듈 초기화 완료")
        except Exception as e:
            logger.error(f"RAG 검색 모듈 초기화 실패: {e}")
            raise RuntimeError(f"RAG 검색 모듈 초기화 실패: {e}")

    def search(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: Optional[float] = None
    ) -> RAGSearchResult:
        """RAG 검색 수행.

        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 문서 수
            score_threshold: 최소 점수 임계값 (None이면 기본값 사용)

        Returns:
            RAGSearchResult: 검색 결과
        """
        self._ensure_initialized()

        threshold = score_threshold or self.score_threshold

        try:
            # 벡터 DB 검색
            results = self._search_func(
                query=query,
                top_k=top_k,
                score_threshold=threshold
            )

            if not results:
                return RAGSearchResult(
                    query=query,
                    documents=[],
                    best_score=0.0,
                    is_confident=False
                )

            # 문서 변환
            documents = [
                RetrievedDocument(
                    content=doc.get("content", ""),
                    source=doc.get("source", "unknown"),
                    page=doc.get("page", 0),
                    score=doc.get("score", 0.0),
                    metadata=doc.get("metadata", {})
                )
                for doc in results
            ]

            # 최고 점수 계산
            best_score = max(doc.score for doc in documents) if documents else 0.0

            # 신뢰도 판단
            is_confident = best_score >= LOW_CONFIDENCE_THRESHOLD

            return RAGSearchResult(
                query=query,
                documents=documents,
                best_score=best_score,
                is_confident=is_confident
            )

        except Exception as e:
            logger.error(f"RAG 검색 오류: {e}", exc_info=True)
            return RAGSearchResult(
                query=query,
                documents=[],
                best_score=0.0,
                is_confident=False,
                error=str(e)
            )

    def search_batch(
        self,
        queries: List[str],
        top_k: int = 3
    ) -> List[RAGSearchResult]:
        """배치 RAG 검색.

        Args:
            queries: 검색 쿼리 리스트
            top_k: 각 쿼리별 반환할 최대 문서 수

        Returns:
            List[RAGSearchResult]: 검색 결과 리스트
        """
        results = []
        for query in queries:
            result = self.search(query, top_k=top_k)
            results.append(result)
        return results

    def evaluate_retrieval(
        self,
        result: RAGSearchResult,
        expected_source: Optional[str] = None,
        expected_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """검색 결과 평가.

        Args:
            result: RAG 검색 결과
            expected_source: 기대하는 문서 출처
            expected_keywords: 기대하는 키워드 리스트

        Returns:
            평가 결과 딕셔너리
        """
        evaluation = {
            "has_results": len(result.documents) > 0,
            "is_confident": result.is_confident,
            "best_score": result.best_score,
            "num_documents": len(result.documents),
            "source_matched": False,
            "keyword_coverage": 0.0
        }

        if not result.documents:
            return evaluation

        # 출처 일치 확인
        if expected_source:
            sources = [doc.source for doc in result.documents]
            evaluation["source_matched"] = any(
                expected_source.lower() in src.lower()
                for src in sources
            )

        # 키워드 커버리지 계산
        if expected_keywords:
            all_content = " ".join(doc.content for doc in result.documents).lower()
            matched_keywords = sum(
                1 for kw in expected_keywords
                if kw.lower() in all_content
            )
            evaluation["keyword_coverage"] = matched_keywords / len(expected_keywords)

        return evaluation

    def get_context_for_answer(
        self,
        result: RAGSearchResult,
        max_chars: int = 2000
    ) -> str:
        """답변 생성을 위한 컨텍스트 추출.

        Args:
            result: RAG 검색 결과
            max_chars: 최대 문자 수

        Returns:
            컨텍스트 문자열
        """
        if not result.documents:
            return ""

        context_parts = []
        total_chars = 0

        for i, doc in enumerate(result.documents):
            # 점수와 출처 정보 포함
            header = f"[문서 {i+1}] (출처: {doc.source}, 유사도: {doc.score:.2f})"
            content = doc.content.strip()

            part_text = f"{header}\n{content}\n"

            if total_chars + len(part_text) > max_chars:
                # 남은 공간만큼만 추가
                remaining = max_chars - total_chars
                if remaining > 100:  # 최소 100자는 있어야 의미가 있음
                    part_text = part_text[:remaining] + "..."
                    context_parts.append(part_text)
                break

            context_parts.append(part_text)
            total_chars += len(part_text)

        return "\n".join(context_parts)

    def calculate_relevance_metrics(
        self,
        results: List[RAGSearchResult]
    ) -> Dict[str, float]:
        """전체 결과에 대한 관련성 메트릭 계산.

        Args:
            results: RAG 검색 결과 리스트

        Returns:
            메트릭 딕셔너리
        """
        if not results:
            return {
                "avg_best_score": 0.0,
                "confidence_rate": 0.0,
                "retrieval_rate": 0.0,
                "avg_num_docs": 0.0
            }

        total_best_scores = sum(r.best_score for r in results)
        confident_count = sum(1 for r in results if r.is_confident)
        retrieval_count = sum(1 for r in results if r.documents)
        total_docs = sum(len(r.documents) for r in results)

        return {
            "avg_best_score": total_best_scores / len(results),
            "confidence_rate": confident_count / len(results),
            "retrieval_rate": retrieval_count / len(results),
            "avg_num_docs": total_docs / len(results)
        }
