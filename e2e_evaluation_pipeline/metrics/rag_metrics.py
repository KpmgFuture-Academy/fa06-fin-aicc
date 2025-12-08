"""
RAG Hybrid Search Metrics Evaluation
====================================

ChromaDB + BM25 + Reranking 하이브리드 검색 성능 평가

평가 지표:
    - Precision@K: Top K 문서 중 정답 포함 비율
    - Recall@K: 정답 문서 중 검색된 비율
    - MRR (Mean Reciprocal Rank): 정답 문서 순위 역수 평균
    - NDCG@K: 순위 가중 정규화 점수
    - BM25 Contribution: BM25 보정 기여도
    - Rerank Effectiveness: Reranking 효과성
    - Faithfulness: 답변의 컨텍스트 충실도
    - Answer Relevancy: 답변의 질문 관련성
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import math

from .base import BaseMetrics, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS


@dataclass
class RAGTestCase:
    """RAG 테스트 케이스"""
    query: str
    relevant_doc_ids: List[str]  # 정답 문서 ID들
    reference_answer: Optional[str] = None  # 참조 답변
    domain: Optional[str] = None


@dataclass
class RetrievedDocument:
    """검색된 문서"""
    doc_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGResult:
    """RAG 검색 결과"""
    query: str
    retrieved_docs: List[RetrievedDocument]
    generated_answer: Optional[str] = None

    # 중간 결과 (Hybrid Search 분석용)
    vector_only_docs: Optional[List[RetrievedDocument]] = None  # BM25 보정 전
    before_rerank_docs: Optional[List[RetrievedDocument]] = None  # Reranking 전


class RAGMetrics(BaseMetrics):
    """RAG Hybrid Search 성능 평가 메트릭"""

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.rag)
        self._financial_keywords: Set[str] = set()

    @property
    def module_name(self) -> str:
        return "RAG Hybrid Search"

    def load_financial_keywords(self, keywords: List[str]):
        """금융 키워드 목록 로드"""
        self._financial_keywords = set(keywords)

    def evaluate(self, data: List[Tuple[RAGTestCase, RAGResult]]) -> EvaluationResult:
        """
        RAG 성능 평가 실행

        Args:
            data: [(테스트케이스, RAG결과), ...] 리스트
        """
        self.reset()
        start_time = datetime.now()

        if not data:
            self.errors.append("No test data provided")
            return self._create_evaluation_result(start_time, {"error": "No data"})

        # 메트릭 계산
        precision_at_3 = []
        recall_at_20 = []
        mrr_scores = []
        ndcg_at_3 = []
        bm25_contributions = []
        rerank_improvements = []
        financial_matches = []
        low_confidence_rates = []
        faithfulness_scores = []
        relevancy_scores = []

        for test_case, result in data:
            try:
                relevant_ids = set(test_case.relevant_doc_ids)
                retrieved_ids = [doc.doc_id for doc in result.retrieved_docs]

                # Precision@3
                p_at_3 = self._calculate_precision_at_k(retrieved_ids, relevant_ids, k=3)
                precision_at_3.append(p_at_3)

                # Recall@20 (벡터 검색 단계)
                if result.vector_only_docs:
                    vector_ids = [doc.doc_id for doc in result.vector_only_docs[:20]]
                    r_at_20 = self._calculate_recall_at_k(vector_ids, relevant_ids, k=20)
                    recall_at_20.append(r_at_20)

                # MRR
                mrr = self._calculate_mrr(retrieved_ids, relevant_ids)
                mrr_scores.append(mrr)

                # NDCG@3
                ndcg = self._calculate_ndcg_at_k(retrieved_ids, relevant_ids, k=3)
                ndcg_at_3.append(ndcg)

                # BM25 Contribution (순위 상승 비율)
                if result.vector_only_docs:
                    bm25_contrib = self._calculate_bm25_contribution(
                        result.vector_only_docs,
                        result.before_rerank_docs or result.retrieved_docs,
                        relevant_ids
                    )
                    bm25_contributions.append(bm25_contrib)

                # Rerank Effectiveness
                if result.before_rerank_docs:
                    rerank_effect = self._calculate_rerank_effectiveness(
                        result.before_rerank_docs,
                        result.retrieved_docs,
                        relevant_ids
                    )
                    rerank_improvements.append(rerank_effect)

                # Financial Keyword Match
                if self._financial_keywords:
                    keyword_match = self._calculate_keyword_match(
                        test_case.query,
                        result.retrieved_docs
                    )
                    financial_matches.append(keyword_match)

                # Low Confidence Rate
                low_conf = self._calculate_low_confidence_rate(result.retrieved_docs)
                low_confidence_rates.append(low_conf)

                # Faithfulness (답변이 있는 경우)
                if result.generated_answer and test_case.reference_answer:
                    faithfulness = self._calculate_faithfulness(
                        result.generated_answer,
                        result.retrieved_docs
                    )
                    faithfulness_scores.append(faithfulness)

                    # Answer Relevancy
                    relevancy = self._calculate_answer_relevancy(
                        test_case.query,
                        result.generated_answer
                    )
                    relevancy_scores.append(relevancy)

            except Exception as e:
                self.errors.append(f"Error processing test case: {str(e)}")

        # 결과 집계
        summary = {
            "total_samples": len(data),
            "processed_samples": len(precision_at_3)
        }

        # Precision@3
        if precision_at_3:
            avg_p3 = sum(precision_at_3) / len(precision_at_3) * 100
            self.results.append(self._create_metric_result(
                "precision_at_3", avg_p3,
                details={"min": min(precision_at_3) * 100, "max": max(precision_at_3) * 100}
            ))
            summary["avg_precision_at_3"] = avg_p3

        # Recall@20
        if recall_at_20:
            avg_r20 = sum(recall_at_20) / len(recall_at_20) * 100
            self.results.append(self._create_metric_result(
                "recall_at_20", avg_r20
            ))

        # MRR
        if mrr_scores:
            avg_mrr = sum(mrr_scores) / len(mrr_scores)
            self.results.append(self._create_metric_result(
                "mrr", avg_mrr
            ))
            summary["avg_mrr"] = avg_mrr

        # NDCG@3
        if ndcg_at_3:
            avg_ndcg = sum(ndcg_at_3) / len(ndcg_at_3)
            self.results.append(self._create_metric_result(
                "ndcg_at_3", avg_ndcg
            ))

        # BM25 Contribution
        if bm25_contributions:
            avg_bm25 = sum(bm25_contributions) / len(bm25_contributions)
            self.results.append(self._create_metric_result(
                "bm25_contribution", avg_bm25
            ))
            summary["avg_bm25_contribution"] = avg_bm25

        # Rerank Effectiveness
        if rerank_improvements:
            avg_rerank = sum(rerank_improvements) / len(rerank_improvements)
            self.results.append(self._create_metric_result(
                "rerank_effectiveness", avg_rerank
            ))
            summary["avg_rerank_effectiveness"] = avg_rerank

        # Financial Keyword Match
        if financial_matches:
            avg_keyword = sum(financial_matches) / len(financial_matches)
            self.results.append(self._create_metric_result(
                "financial_keyword_match", avg_keyword
            ))

        # Low Confidence Rate
        if low_confidence_rates:
            avg_low_conf = sum(low_confidence_rates) / len(low_confidence_rates)
            self.results.append(self._create_metric_result(
                "low_confidence_rate", avg_low_conf
            ))

        # Faithfulness
        if faithfulness_scores:
            avg_faith = sum(faithfulness_scores) / len(faithfulness_scores)
            self.results.append(self._create_metric_result(
                "faithfulness", avg_faith
            ))
            summary["avg_faithfulness"] = avg_faith

        # Answer Relevancy
        if relevancy_scores:
            avg_rel = sum(relevancy_scores) / len(relevancy_scores)
            self.results.append(self._create_metric_result(
                "answer_relevancy", avg_rel
            ))

        return self._create_evaluation_result(start_time, summary)

    def _calculate_precision_at_k(
        self,
        retrieved_ids: List[str],
        relevant_ids: Set[str],
        k: int
    ) -> float:
        """Precision@K 계산"""
        if k <= 0:
            return 0.0

        top_k = retrieved_ids[:k]
        if not top_k:
            return 0.0

        relevant_in_top_k = sum(1 for doc_id in top_k if doc_id in relevant_ids)
        return relevant_in_top_k / len(top_k)

    def _calculate_recall_at_k(
        self,
        retrieved_ids: List[str],
        relevant_ids: Set[str],
        k: int
    ) -> float:
        """Recall@K 계산"""
        if not relevant_ids:
            return 1.0

        top_k = set(retrieved_ids[:k])
        found = len(top_k & relevant_ids)
        return found / len(relevant_ids)

    def _calculate_mrr(
        self,
        retrieved_ids: List[str],
        relevant_ids: Set[str]
    ) -> float:
        """Mean Reciprocal Rank 계산"""
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_ids:
                return 1.0 / (i + 1)
        return 0.0

    def _calculate_ndcg_at_k(
        self,
        retrieved_ids: List[str],
        relevant_ids: Set[str],
        k: int
    ) -> float:
        """NDCG@K 계산"""
        def dcg(relevances: List[int]) -> float:
            return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))

        # 실제 관련성 점수 (이진: 0 또는 1)
        relevances = [1 if doc_id in relevant_ids else 0 for doc_id in retrieved_ids[:k]]

        # 이상적인 관련성 (모든 관련 문서가 상위에)
        ideal_relevances = sorted(relevances, reverse=True)

        actual_dcg = dcg(relevances)
        ideal_dcg = dcg(ideal_relevances)

        if ideal_dcg == 0:
            return 0.0

        return actual_dcg / ideal_dcg

    def _calculate_bm25_contribution(
        self,
        vector_only_docs: List[RetrievedDocument],
        after_bm25_docs: List[RetrievedDocument],
        relevant_ids: Set[str]
    ) -> float:
        """BM25 보정으로 순위가 상승한 정답 문서 비율"""
        if not relevant_ids:
            return 0.0

        improvements = 0
        vector_ranks = {doc.doc_id: i for i, doc in enumerate(vector_only_docs)}
        after_ranks = {doc.doc_id: i for i, doc in enumerate(after_bm25_docs)}

        for doc_id in relevant_ids:
            if doc_id in vector_ranks and doc_id in after_ranks:
                if after_ranks[doc_id] < vector_ranks[doc_id]:
                    improvements += 1

        return (improvements / len(relevant_ids)) * 100

    def _calculate_rerank_effectiveness(
        self,
        before_rerank: List[RetrievedDocument],
        after_rerank: List[RetrievedDocument],
        relevant_ids: Set[str]
    ) -> float:
        """Reranking으로 순위가 개선된 비율"""
        if not relevant_ids:
            return 0.0

        improvements = 0
        before_ranks = {doc.doc_id: i for i, doc in enumerate(before_rerank)}
        after_ranks = {doc.doc_id: i for i, doc in enumerate(after_rerank)}

        for doc_id in relevant_ids:
            if doc_id in before_ranks and doc_id in after_ranks:
                if after_ranks[doc_id] < before_ranks[doc_id]:
                    improvements += 1

        return (improvements / len(relevant_ids)) * 100

    def _calculate_keyword_match(
        self,
        query: str,
        retrieved_docs: List[RetrievedDocument]
    ) -> float:
        """금융 키워드 매칭률"""
        # 쿼리에서 금융 키워드 추출
        query_keywords = set()
        for keyword in self._financial_keywords:
            if keyword in query:
                query_keywords.add(keyword)

        if not query_keywords:
            return 100.0

        # 검색 결과에서 키워드 포함 여부
        found = 0
        for keyword in query_keywords:
            for doc in retrieved_docs:
                if keyword in doc.content:
                    found += 1
                    break

        return (found / len(query_keywords)) * 100

    def _calculate_low_confidence_rate(
        self,
        retrieved_docs: List[RetrievedDocument],
        threshold: float = 0.5
    ) -> float:
        """낮은 신뢰도 결과 비율"""
        if not retrieved_docs:
            return 0.0

        low_confidence = sum(1 for doc in retrieved_docs if doc.score < threshold)
        return (low_confidence / len(retrieved_docs)) * 100

    def _calculate_faithfulness(
        self,
        generated_answer: str,
        retrieved_docs: List[RetrievedDocument]
    ) -> float:
        """
        답변의 컨텍스트 충실도 (간단 버전)
        실제로는 RAGAS 등 사용 권장
        """
        if not generated_answer or not retrieved_docs:
            return 0.0

        # 간단한 토큰 기반 오버랩
        answer_tokens = set(generated_answer.lower().split())
        context_tokens = set()
        for doc in retrieved_docs:
            context_tokens.update(doc.content.lower().split())

        if not answer_tokens:
            return 0.0

        overlap = len(answer_tokens & context_tokens)
        return overlap / len(answer_tokens)

    def _calculate_answer_relevancy(
        self,
        query: str,
        generated_answer: str
    ) -> float:
        """
        답변의 질문 관련성 (간단 버전)
        실제로는 RAGAS 등 사용 권장
        """
        if not query or not generated_answer:
            return 0.0

        query_tokens = set(query.lower().split())
        answer_tokens = set(generated_answer.lower().split())

        if not query_tokens:
            return 0.0

        overlap = len(query_tokens & answer_tokens)
        return overlap / len(query_tokens)


def evaluate_rag_from_golden_set(
    golden_qa_path: str,
    vector_store: Any,
    top_k: int = 3
) -> EvaluationResult:
    """
    Golden QA 셋 기반 RAG 평가 헬퍼 함수

    Args:
        golden_qa_path: Golden QA JSON 경로
        vector_store: 벡터 스토어 인스턴스
        top_k: 검색할 문서 수
    """
    import json

    # Golden QA 로드
    with open(golden_qa_path, 'r', encoding='utf-8') as f:
        golden_qa = json.load(f)

    eval_data = []
    for item in golden_qa:
        test_case = RAGTestCase(
            query=item["query"],
            relevant_doc_ids=item["relevant_doc_ids"],
            reference_answer=item.get("reference_answer"),
            domain=item.get("domain")
        )

        # RAG 검색 실행
        results = vector_store.search_documents(item["query"], top_k=top_k)

        retrieved_docs = [
            RetrievedDocument(
                doc_id=r.get("id", str(i)),
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                metadata=r.get("metadata", {})
            )
            for i, r in enumerate(results)
        ]

        rag_result = RAGResult(
            query=item["query"],
            retrieved_docs=retrieved_docs
        )

        eval_data.append((test_case, rag_result))

    metrics = RAGMetrics()
    return metrics.evaluate(eval_data)
