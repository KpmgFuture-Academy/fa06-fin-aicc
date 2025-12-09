"""
STT (Speech-to-Text) Metrics Evaluation
=======================================

VITO STT 성능 평가 메트릭

평가 지표:
    - CER (Character Error Rate): 한국어 문자 오류율
    - WER (Word Error Rate): 단어 오류율
    - Segmentation Count: 분절 수 (요약 품질 직결)
    - Financial Term Accuracy: 금융 전문용어 인식률
    - Speaker Diarization Accuracy: 화자 분리 정확도
    - Latency (TTFB): 첫 응답까지 시간
"""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import re

from .base import BaseMetrics, MetricResult, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS


@dataclass
class STTTestCase:
    """STT 테스트 케이스"""
    audio_path: str
    reference_text: str
    expected_segments: Optional[int] = None
    speaker_labels: Optional[List[str]] = None  # 화자 레이블 (예: ["agent", "customer"])
    financial_terms: Optional[List[str]] = None  # 포함된 금융 용어


@dataclass
class STTResult:
    """STT 결과"""
    transcribed_text: str
    segments: List[Dict[str, Any]]
    latency_ms: float
    speaker_mapping: Optional[Dict[str, str]] = None


class STTMetrics(BaseMetrics):
    """STT 성능 평가 메트릭"""

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.stt)
        self._financial_terms: List[str] = []

    @property
    def module_name(self) -> str:
        return "STT"

    def load_financial_terms(self, terms: List[str]):
        """금융 전문용어 목록 로드"""
        self._financial_terms = terms

    def evaluate(self, data: List[Tuple[STTTestCase, STTResult]]) -> EvaluationResult:
        """
        STT 성능 평가 실행

        Args:
            data: [(테스트케이스, STT결과), ...] 리스트
        """
        self.reset()
        start_time = datetime.now()

        if not data:
            self.errors.append("No test data provided")
            return self._create_evaluation_result(start_time, {"error": "No data"})

        # 메트릭 계산
        cer_scores = []
        wer_scores = []
        segment_counts = []
        wrong_segments = []
        financial_accuracies = []
        diarization_accuracies = []
        latencies = []

        for test_case, result in data:
            try:
                # CER 계산
                cer = self._calculate_cer(test_case.reference_text, result.transcribed_text)
                cer_scores.append(cer)

                # WER 계산
                wer = self._calculate_wer(test_case.reference_text, result.transcribed_text)
                wer_scores.append(wer)

                # Segmentation 분석
                segment_count = len(result.segments)
                segment_counts.append(segment_count)

                # 잘못된 분절 비율 (예상 대비)
                if test_case.expected_segments:
                    wrong_ratio = max(0, segment_count - test_case.expected_segments) / max(segment_count, 1)
                    wrong_segments.append(wrong_ratio * 100)

                # 금융 전문용어 인식률
                if test_case.financial_terms:
                    term_accuracy = self._calculate_financial_term_accuracy(
                        result.transcribed_text,
                        test_case.financial_terms
                    )
                    financial_accuracies.append(term_accuracy)

                # 화자 분리 정확도
                if test_case.speaker_labels and result.speaker_mapping:
                    diarization_acc = self._calculate_diarization_accuracy(
                        test_case.speaker_labels,
                        result.segments
                    )
                    diarization_accuracies.append(diarization_acc)

                # Latency
                latencies.append(result.latency_ms)

            except Exception as e:
                self.errors.append(f"Error processing test case: {str(e)}")

        # 결과 집계
        summary = {
            "total_samples": len(data),
            "processed_samples": len(cer_scores)
        }

        # CER
        if cer_scores:
            avg_cer = sum(cer_scores) / len(cer_scores)
            self.results.append(self._create_metric_result(
                "cer", avg_cer,
                details={"min": min(cer_scores), "max": max(cer_scores), "samples": len(cer_scores)}
            ))
            summary["avg_cer"] = avg_cer

        # WER
        if wer_scores:
            avg_wer = sum(wer_scores) / len(wer_scores)
            self.results.append(self._create_metric_result(
                "wer", avg_wer,
                details={"min": min(wer_scores), "max": max(wer_scores), "samples": len(wer_scores)}
            ))
            summary["avg_wer"] = avg_wer

        # Segmentation Count
        if segment_counts:
            avg_segments = sum(segment_counts) / len(segment_counts)
            self.results.append(self._create_metric_result(
                "segmentation_count", avg_segments,
                details={"min": min(segment_counts), "max": max(segment_counts)}
            ))
            summary["avg_segmentation_count"] = avg_segments

        # Wrong Segmentation Rate
        if wrong_segments:
            avg_wrong = sum(wrong_segments) / len(wrong_segments)
            self.results.append(self._create_metric_result(
                "wrong_segmentation_rate", avg_wrong
            ))

        # Financial Term Accuracy
        if financial_accuracies:
            avg_financial = sum(financial_accuracies) / len(financial_accuracies)
            self.results.append(self._create_metric_result(
                "financial_term_accuracy", avg_financial
            ))
            summary["avg_financial_term_accuracy"] = avg_financial

        # Speaker Diarization Accuracy
        if diarization_accuracies:
            avg_diarization = sum(diarization_accuracies) / len(diarization_accuracies)
            self.results.append(self._create_metric_result(
                "speaker_diarization_accuracy", avg_diarization
            ))

        # Latency
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            self.results.append(self._create_metric_result(
                "latency_ttfb", avg_latency,
                details={"min": min(latencies), "max": max(latencies), "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]}
            ))
            summary["avg_latency_ms"] = avg_latency

        return self._create_evaluation_result(start_time, summary)

    def _calculate_cer(self, reference: str, hypothesis: str) -> float:
        """
        Character Error Rate 계산

        CER = (S + D + I) / N
        S: 대체(Substitution), D: 삭제(Deletion), I: 삽입(Insertion)
        N: 참조 문자 수
        """
        # 공백 제거 및 정규화
        ref = self._normalize_text(reference)
        hyp = self._normalize_text(hypothesis)

        # Levenshtein distance 계산
        distance = self._levenshtein_distance(ref, hyp)

        if len(ref) == 0:
            return 0.0 if len(hyp) == 0 else 100.0

        return (distance / len(ref)) * 100

    def _calculate_wer(self, reference: str, hypothesis: str) -> float:
        """
        Word Error Rate 계산
        """
        ref_words = self._normalize_text(reference).split()
        hyp_words = self._normalize_text(hypothesis).split()

        distance = self._levenshtein_distance(ref_words, hyp_words)

        if len(ref_words) == 0:
            return 0.0 if len(hyp_words) == 0 else 100.0

        return (distance / len(ref_words)) * 100

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        # 소문자 변환, 특수문자 제거
        text = text.lower()
        text = re.sub(r'[^\w\s가-힣]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _levenshtein_distance(self, s1, s2) -> int:
        """Levenshtein 거리 계산 (동적 프로그래밍)"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # 삽입, 삭제, 대체 비용
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _calculate_financial_term_accuracy(
        self,
        transcribed_text: str,
        expected_terms: List[str]
    ) -> float:
        """금융 전문용어 인식률 계산"""
        if not expected_terms:
            return 100.0

        text_normalized = self._normalize_text(transcribed_text)
        found_count = 0

        for term in expected_terms:
            term_normalized = self._normalize_text(term)
            if term_normalized in text_normalized:
                found_count += 1

        return (found_count / len(expected_terms)) * 100

    def _calculate_diarization_accuracy(
        self,
        expected_labels: List[str],
        segments: List[Dict[str, Any]]
    ) -> float:
        """화자 분리 정확도 계산"""
        if not segments or not expected_labels:
            return 0.0

        # 세그먼트에서 화자 레이블 추출
        segment_speakers = [s.get("speaker", "") for s in segments if s.get("speaker")]

        if not segment_speakers:
            return 0.0

        # 간단한 매칭 (실제로는 더 정교한 알고리즘 필요)
        unique_detected = set(segment_speakers)
        unique_expected = set(expected_labels)

        # 감지된 화자 수와 예상 화자 수 비교
        if len(unique_detected) == len(unique_expected):
            return 100.0
        elif len(unique_detected) > 0:
            return (min(len(unique_detected), len(unique_expected)) / max(len(unique_detected), len(unique_expected))) * 100
        else:
            return 0.0


def evaluate_stt_from_files(
    audio_dir: str,
    reference_file: str,
    stt_service: Any,
    financial_terms: Optional[List[str]] = None
) -> EvaluationResult:
    """
    파일 기반 STT 평가 헬퍼 함수

    Args:
        audio_dir: 오디오 파일 디렉토리
        reference_file: 참조 텍스트 파일 (JSON)
        stt_service: STT 서비스 인스턴스
        financial_terms: 금융 전문용어 목록
    """
    import json
    from pathlib import Path

    metrics = STTMetrics()
    if financial_terms:
        metrics.load_financial_terms(financial_terms)

    # 테스트 데이터 로드
    with open(reference_file, 'r', encoding='utf-8') as f:
        references = json.load(f)

    test_data = []
    audio_path = Path(audio_dir)

    for ref in references:
        audio_file = audio_path / ref["audio_file"]
        if not audio_file.exists():
            continue

        test_case = STTTestCase(
            audio_path=str(audio_file),
            reference_text=ref["text"],
            expected_segments=ref.get("expected_segments"),
            speaker_labels=ref.get("speakers"),
            financial_terms=ref.get("financial_terms", [])
        )

        # STT 실행
        start_time = time.time()
        try:
            stt_result = stt_service.transcribe_file(str(audio_file))
            latency = (time.time() - start_time) * 1000

            result = STTResult(
                transcribed_text=stt_result.text,
                segments=[{"text": s.text, "speaker": getattr(s, "speaker", None)}
                         for s in stt_result.segments],
                latency_ms=latency
            )

            test_data.append((test_case, result))
        except Exception as e:
            print(f"Error processing {audio_file}: {e}")

    return metrics.evaluate(test_data)
