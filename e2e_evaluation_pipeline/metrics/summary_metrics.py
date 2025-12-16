"""
Summary Agent Metrics Evaluation
================================

요약 에이전트 성능 평가

평가 지표:
    - ROUGE-L: 참조 요약 대비 LCS 기반 일치도
    - ROUGE-1: 단어 단위 일치도
    - ROUGE-2: 바이그램 일치도
    - Information Omission Rate: 핵심 정보 누락 비율
    - Hallucination Rate: 환각 (없는 정보 추가) 비율
    - Sentiment Accuracy: 감정 분류 정확도
    - Keyword Accuracy: 키워드 추출 정확도
    - Repeat Explanation Rate: 상담원 반복 설명 요청률
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import Counter

from .base import BaseMetrics, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS


@dataclass
class SummaryTestCase:
    """Summary 테스트 케이스"""
    dialogue_id: str
    conversation: List[Dict[str, str]]  # 원본 대화
    reference_summary: str  # 참조 요약
    key_information: List[str]  # 반드시 포함해야 할 핵심 정보
    true_sentiment: str  # 실제 감정 (POSITIVE/NEGATIVE/NEUTRAL)
    true_keywords: List[str]  # 실제 핵심 키워드


@dataclass
class SummaryResult:
    """Summary 결과"""
    generated_summary: str
    predicted_sentiment: str
    extracted_keywords: List[str]
    agent_satisfaction_score: Optional[float] = None  # 상담원 평가 (1-5)
    required_repeat_explanation: bool = False  # 상담원이 고객에게 다시 물어봄


class SummaryMetrics(BaseMetrics):
    """Summary 성능 평가 메트릭"""

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.summary)

    @property
    def module_name(self) -> str:
        return "Summary Agent"

    def evaluate(self, data: List[Tuple[SummaryTestCase, SummaryResult]]) -> EvaluationResult:
        """
        Summary 성능 평가 실행

        Args:
            data: [(테스트케이스, 결과), ...] 리스트
        """
        self.reset()
        start_time = datetime.now()

        if not data:
            self.errors.append("No test data provided")
            return self._create_evaluation_result(start_time, {"error": "No data"})

        # 메트릭 계산
        rouge_l_scores = []
        rouge_1_scores = []
        rouge_2_scores = []
        omission_rates = []
        hallucination_rates = []
        sentiment_correct = []
        keyword_accuracies = []
        satisfaction_scores = []
        repeat_explanations = []

        for test_case, result in data:
            try:
                # ROUGE scores
                rouge_scores = self._calculate_rouge_scores(
                    test_case.reference_summary,
                    result.generated_summary
                )
                rouge_l_scores.append(rouge_scores["rouge_l"])
                rouge_1_scores.append(rouge_scores["rouge_1"])
                rouge_2_scores.append(rouge_scores["rouge_2"])

                # Information Omission Rate
                omission = self._calculate_omission_rate(
                    test_case.key_information,
                    result.generated_summary
                )
                omission_rates.append(omission)

                # Hallucination Rate
                hallucination = self._calculate_hallucination_rate(
                    test_case.conversation,
                    result.generated_summary
                )
                hallucination_rates.append(hallucination)

                # Sentiment Accuracy
                sentiment_match = 1 if test_case.true_sentiment.upper() == result.predicted_sentiment.upper() else 0
                sentiment_correct.append(sentiment_match)

                # Keyword Accuracy
                keyword_acc = self._calculate_keyword_accuracy(
                    test_case.true_keywords,
                    result.extracted_keywords
                )
                keyword_accuracies.append(keyword_acc)

                # Agent Satisfaction (있는 경우)
                if result.agent_satisfaction_score is not None:
                    satisfaction_scores.append(result.agent_satisfaction_score)

                # Repeat Explanation
                repeat_explanations.append(1 if result.required_repeat_explanation else 0)

            except Exception as e:
                self.errors.append(f"Error processing dialogue {test_case.dialogue_id}: {str(e)}")

        # 결과 집계
        summary = {
            "total_samples": len(data),
            "processed_samples": len(rouge_l_scores)
        }

        # ROUGE-L
        if rouge_l_scores:
            avg_rouge_l = sum(rouge_l_scores) / len(rouge_l_scores)
            self.results.append(self._create_metric_result(
                "rouge_l", avg_rouge_l,
                details={"min": min(rouge_l_scores), "max": max(rouge_l_scores)}
            ))
            summary["avg_rouge_l"] = avg_rouge_l

        # ROUGE-1
        if rouge_1_scores:
            avg_rouge_1 = sum(rouge_1_scores) / len(rouge_1_scores)
            self.results.append(self._create_metric_result(
                "rouge_1", avg_rouge_1
            ))

        # ROUGE-2
        if rouge_2_scores:
            avg_rouge_2 = sum(rouge_2_scores) / len(rouge_2_scores)
            self.results.append(self._create_metric_result(
                "rouge_2", avg_rouge_2
            ))

        # Information Omission Rate
        if omission_rates:
            avg_omission = sum(omission_rates) / len(omission_rates)
            self.results.append(self._create_metric_result(
                "info_omission_rate", avg_omission
            ))
            summary["avg_omission_rate"] = avg_omission

        # Hallucination Rate
        if hallucination_rates:
            avg_hallucination = sum(hallucination_rates) / len(hallucination_rates)
            self.results.append(self._create_metric_result(
                "hallucination_rate", avg_hallucination
            ))

        # Sentiment Accuracy
        if sentiment_correct:
            sentiment_acc = (sum(sentiment_correct) / len(sentiment_correct)) * 100
            self.results.append(self._create_metric_result(
                "sentiment_accuracy", sentiment_acc
            ))
            summary["sentiment_accuracy"] = sentiment_acc

        # Keyword Accuracy
        if keyword_accuracies:
            avg_keyword = sum(keyword_accuracies) / len(keyword_accuracies)
            self.results.append(self._create_metric_result(
                "keyword_accuracy", avg_keyword
            ))

        # Agent Satisfaction
        if satisfaction_scores:
            avg_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores)
            self.results.append(self._create_metric_result(
                "agent_satisfaction", avg_satisfaction
            ))
            summary["avg_agent_satisfaction"] = avg_satisfaction

        # Repeat Explanation Rate
        if repeat_explanations:
            repeat_rate = (sum(repeat_explanations) / len(repeat_explanations)) * 100
            self.results.append(self._create_metric_result(
                "repeat_explanation_rate", repeat_rate
            ))
            summary["repeat_explanation_rate"] = repeat_rate

        return self._create_evaluation_result(start_time, summary)

    def _calculate_rouge_scores(
        self,
        reference: str,
        hypothesis: str
    ) -> Dict[str, float]:
        """ROUGE 점수 계산"""
        # 토큰화
        ref_tokens = self._tokenize(reference)
        hyp_tokens = self._tokenize(hypothesis)

        # ROUGE-1 (Unigram)
        rouge_1 = self._calculate_rouge_n(ref_tokens, hyp_tokens, n=1)

        # ROUGE-2 (Bigram)
        rouge_2 = self._calculate_rouge_n(ref_tokens, hyp_tokens, n=2)

        # ROUGE-L (LCS)
        rouge_l = self._calculate_rouge_l(ref_tokens, hyp_tokens)

        return {
            "rouge_1": rouge_1,
            "rouge_2": rouge_2,
            "rouge_l": rouge_l
        }

    def _tokenize(self, text: str) -> List[str]:
        """텍스트 토큰화"""
        import re
        # 한국어 + 영어 토큰화
        text = text.lower()
        # 특수문자 제거 (한글, 영어, 숫자만 유지)
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        tokens = text.split()
        return [t for t in tokens if t]

    def _calculate_rouge_n(
        self,
        reference: List[str],
        hypothesis: List[str],
        n: int
    ) -> float:
        """ROUGE-N 점수 계산"""
        def get_ngrams(tokens: List[str], n: int) -> Counter:
            ngrams = []
            for i in range(len(tokens) - n + 1):
                ngrams.append(tuple(tokens[i:i+n]))
            return Counter(ngrams)

        ref_ngrams = get_ngrams(reference, n)
        hyp_ngrams = get_ngrams(hypothesis, n)

        if not ref_ngrams or not hyp_ngrams:
            return 0.0

        # 교집합
        overlap = sum((ref_ngrams & hyp_ngrams).values())

        # Precision
        precision = overlap / sum(hyp_ngrams.values()) if hyp_ngrams else 0

        # Recall
        recall = overlap / sum(ref_ngrams.values()) if ref_ngrams else 0

        # F1
        if precision + recall == 0:
            return 0.0

        f1 = 2 * precision * recall / (precision + recall)
        return f1

    def _calculate_rouge_l(
        self,
        reference: List[str],
        hypothesis: List[str]
    ) -> float:
        """ROUGE-L 점수 계산 (LCS 기반)"""
        if not reference or not hypothesis:
            return 0.0

        # LCS 길이 계산
        lcs_length = self._lcs_length(reference, hypothesis)

        # Precision
        precision = lcs_length / len(hypothesis) if hypothesis else 0

        # Recall
        recall = lcs_length / len(reference) if reference else 0

        # F1
        if precision + recall == 0:
            return 0.0

        f1 = 2 * precision * recall / (precision + recall)
        return f1

    def _lcs_length(self, x: List[str], y: List[str]) -> int:
        """최장 공통 부분 수열 (LCS) 길이"""
        m, n = len(x), len(y)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if x[i-1] == y[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])

        return dp[m][n]

    def _calculate_omission_rate(
        self,
        key_information: List[str],
        generated_summary: str
    ) -> float:
        """핵심 정보 누락률"""
        if not key_information:
            return 0.0

        summary_lower = generated_summary.lower()
        omitted = 0

        for info in key_information:
            info_lower = info.lower()
            # 핵심 정보가 요약에 포함되어 있는지 확인
            if info_lower not in summary_lower:
                # 토큰 기반 확인
                info_tokens = set(self._tokenize(info))
                summary_tokens = set(self._tokenize(generated_summary))
                overlap = len(info_tokens & summary_tokens)
                if overlap < len(info_tokens) * 0.5:  # 50% 미만 매칭
                    omitted += 1

        return (omitted / len(key_information)) * 100

    def _calculate_hallucination_rate(
        self,
        conversation: List[Dict[str, str]],
        generated_summary: str
    ) -> float:
        """환각률 (대화에 없는 정보 비율)"""
        # 대화에서 모든 정보 추출
        conversation_text = " ".join([
            turn.get("content", "") for turn in conversation
        ])
        conversation_tokens = set(self._tokenize(conversation_text))

        # 요약 토큰
        summary_tokens = set(self._tokenize(generated_summary))

        if not summary_tokens:
            return 0.0

        # 대화에 없는 토큰
        # (단, 일반적인 단어는 제외 - 조사, 접속사 등)
        common_words = {"의", "가", "이", "은", "는", "을", "를", "에", "와", "과",
                       "및", "등", "있", "없", "하", "합", "됨", "됩", "니다",
                       "요", "고", "로", "으로", "에서", "대한", "위한"}

        meaningful_tokens = summary_tokens - common_words
        new_tokens = meaningful_tokens - conversation_tokens - common_words

        if not meaningful_tokens:
            return 0.0

        # 새로운 토큰 중 환각으로 볼 수 있는 비율
        # (실제로는 더 정교한 판단 필요)
        hallucination_rate = (len(new_tokens) / len(meaningful_tokens)) * 100

        # 상한 설정 (100% 이하)
        return min(hallucination_rate, 100.0)

    def _calculate_keyword_accuracy(
        self,
        true_keywords: List[str],
        extracted_keywords: List[str]
    ) -> float:
        """키워드 추출 정확도"""
        if not true_keywords:
            return 100.0 if not extracted_keywords else 0.0

        if not extracted_keywords:
            return 0.0

        # 정규화
        true_set = set(k.lower().strip() for k in true_keywords)
        extracted_set = set(k.lower().strip() for k in extracted_keywords)

        # 교집합
        correct = len(true_set & extracted_set)

        # Precision 기반 (추출한 것 중 맞은 비율)
        precision = (correct / len(extracted_set)) * 100 if extracted_set else 0

        # Recall 기반 (정답 중 추출한 비율)
        recall = (correct / len(true_set)) * 100 if true_set else 0

        # F1 기반 평균
        if precision + recall == 0:
            return 0.0

        return 2 * precision * recall / (precision + recall)


def evaluate_summary_with_rouge_library(
    test_data_path: str
) -> EvaluationResult:
    """
    rouge 라이브러리를 사용한 Summary 평가

    Args:
        test_data_path: 테스트 데이터 JSON 경로
    """
    import json

    # 테스트 데이터 로드
    with open(test_data_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    eval_data = []
    for item in test_data:
        test_case = SummaryTestCase(
            dialogue_id=item.get("id", ""),
            conversation=item.get("conversation", []),
            reference_summary=item["reference_summary"],
            key_information=item.get("key_information", []),
            true_sentiment=item.get("sentiment", "NEUTRAL"),
            true_keywords=item.get("keywords", [])
        )

        result = SummaryResult(
            generated_summary=item.get("generated_summary", ""),
            predicted_sentiment=item.get("predicted_sentiment", "NEUTRAL"),
            extracted_keywords=item.get("extracted_keywords", []),
            agent_satisfaction_score=item.get("agent_score"),
            required_repeat_explanation=item.get("repeat_required", False)
        )

        eval_data.append((test_case, result))

    metrics = SummaryMetrics()
    return metrics.evaluate(eval_data)
