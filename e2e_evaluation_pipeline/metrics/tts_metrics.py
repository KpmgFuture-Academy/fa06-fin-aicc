"""
TTS (Text-to-Speech) Metrics Evaluation
=======================================

Google TTS / OpenAI TTS 성능 평가 메트릭

평가 지표:
    - Synthesis Latency: 음성 합성 시간
    - Characters Per Second: 초당 처리 문자 수
    - Success Rate: 합성 성공률
    - Audio Quality: 오디오 품질 (크기 기반)
"""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .base import BaseMetrics, MetricResult, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS


@dataclass
class TTSTestCase:
    """TTS 테스트 케이스"""
    text: str
    voice: Optional[str] = None
    format: str = "mp3"
    expected_min_audio_size: int = 1000  # 최소 오디오 크기 (bytes)


@dataclass
class TTSResult:
    """TTS 결과"""
    text: str
    audio_bytes: bytes
    synthesis_time_ms: float
    voice: str
    format: str
    success: bool
    error: Optional[str] = None


class TTSMetrics(BaseMetrics):
    """TTS 성능 평가 메트릭"""

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.tts)

    @property
    def module_name(self) -> str:
        return "TTS"

    def evaluate(self, data: List[Tuple[TTSTestCase, TTSResult]]) -> EvaluationResult:
        """
        TTS 성능 평가 실행

        Args:
            data: [(테스트케이스, TTS결과), ...] 리스트
        """
        self.reset()
        start_time = datetime.now()

        if not data:
            self.errors.append("No test data provided")
            return self._create_evaluation_result(start_time, {"error": "No data"})

        # 메트릭 계산
        latencies = []
        chars_per_second_list = []
        success_flags = []
        audio_sizes = []

        for test_case, result in data:
            try:
                # Success Rate
                success_flags.append(1 if result.success else 0)

                if result.success:
                    # Synthesis Latency
                    latencies.append(result.synthesis_time_ms)

                    # Characters Per Second
                    text_length = len(test_case.text.replace(" ", ""))
                    if result.synthesis_time_ms > 0:
                        cps = text_length / (result.synthesis_time_ms / 1000)
                        chars_per_second_list.append(cps)

                    # Audio Size
                    audio_sizes.append(len(result.audio_bytes))

            except Exception as e:
                self.errors.append(f"Error processing test case: {str(e)}")

        # 결과 집계
        summary = {
            "total_samples": len(data),
            "processed_samples": len(success_flags)
        }

        # Success Rate
        if success_flags:
            success_rate = (sum(success_flags) / len(success_flags)) * 100
            self.results.append(self._create_metric_result(
                "success_rate", success_rate,
                details={"succeeded": sum(success_flags), "total": len(success_flags)}
            ))
            summary["success_rate"] = success_rate

        # Synthesis Latency
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            self.results.append(self._create_metric_result(
                "synthesis_latency", avg_latency,
                details={
                    "min": min(latencies),
                    "max": max(latencies),
                    "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
                }
            ))
            summary["avg_synthesis_latency_ms"] = avg_latency

        # Characters Per Second
        if chars_per_second_list:
            avg_cps = sum(chars_per_second_list) / len(chars_per_second_list)
            self.results.append(self._create_metric_result(
                "chars_per_second", avg_cps,
                details={"min": min(chars_per_second_list), "max": max(chars_per_second_list)}
            ))
            summary["avg_chars_per_second"] = avg_cps

        # Audio Quality (based on size ratio)
        if audio_sizes:
            avg_audio_size = sum(audio_sizes) / len(audio_sizes)
            # 텍스트 길이 대비 오디오 크기 비율 (bytes per char)
            text_lengths = [len(tc.text) for tc, _ in data if len(tc.text) > 0]
            if text_lengths:
                avg_text_len = sum(text_lengths) / len(text_lengths)
                bytes_per_char = avg_audio_size / avg_text_len if avg_text_len > 0 else 0
                self.results.append(self._create_metric_result(
                    "audio_quality_ratio", bytes_per_char,
                    details={
                        "avg_audio_size_bytes": avg_audio_size,
                        "avg_text_length": avg_text_len
                    }
                ))
                summary["bytes_per_char"] = bytes_per_char

        return self._create_evaluation_result(start_time, summary)


def evaluate_tts_from_adapter(
    texts: List[str],
    use_google: bool = True,
    voice: Optional[str] = None
) -> EvaluationResult:
    """
    TTS 어댑터를 사용한 평가 헬퍼 함수

    Args:
        texts: 테스트할 텍스트 리스트
        use_google: Google TTS 사용 여부
        voice: 사용할 음성

    Returns:
        EvaluationResult: 평가 결과
    """
    from ..adapters.tts_adapter import TTSAdapter

    metrics = TTSMetrics()
    adapter = TTSAdapter(use_google=use_google)

    test_data = []
    for text in texts:
        test_case = TTSTestCase(text=text, voice=voice)

        start_time = time.time()
        try:
            result = adapter.synthesize(text, voice=voice)
            synthesis_time = (time.time() - start_time) * 1000

            tts_result = TTSResult(
                text=text,
                audio_bytes=result.audio,
                synthesis_time_ms=synthesis_time,
                voice=result.voice,
                format=result.format,
                success=result.error is None,
                error=result.error
            )
        except Exception as e:
            tts_result = TTSResult(
                text=text,
                audio_bytes=b"",
                synthesis_time_ms=0,
                voice=voice or "",
                format="mp3",
                success=False,
                error=str(e)
            )

        test_data.append((test_case, tts_result))

    return metrics.evaluate(test_data)
