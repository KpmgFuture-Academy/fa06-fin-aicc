"""
TTS (Text-to-Speech) Metrics Evaluation
=======================================

Google TTS / OpenAI TTS 성능 평가 메트릭

평가 지표:
    - Synthesis Time: 음성 합성 시간 (latency)
    - Success Rate: 성공률
    - Audio Quality: 오디오 품질 (파일 크기, 포맷)
    - Characters per Second: 초당 문자 처리 속도
    - Error Rate: 오류 발생률
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .base import BaseMetrics, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS
from ..adapters.tts_adapter import TTSResult, TTSEvaluationResult


@dataclass
class TTSTestCase:
    """TTS 테스트 케이스"""
    text: str
    expected_duration_sec: Optional[float] = None  # 예상 음성 길이
    voice: Optional[str] = None
    format: str = "mp3"


@dataclass
class TTSMetricResult:
    """TTS 평가 결과"""
    audio: bytes
    text: str
    voice: str
    format: str
    synthesis_time_ms: float
    audio_size_bytes: int
    success: bool
    error: Optional[str] = None


class TTSMetrics(BaseMetrics):
    """TTS 성능 평가 메트릭"""

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.get("tts", {}))
        self._chars_per_second_target = 5.0  # 한국어 기준 초당 약 5자

    @property
    def module_name(self) -> str:
        return "TTS"

    def evaluate(self, data: List[Tuple[TTSTestCase, TTSMetricResult]]) -> EvaluationResult:
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
        synthesis_times = []
        success_count = 0
        audio_sizes = []
        chars_per_second_list = []
        errors = []

        for test_case, result in data:
            try:
                # Synthesis Time
                synthesis_times.append(result.synthesis_time_ms)

                # Success Rate
                if result.success:
                    success_count += 1
                else:
                    errors.append(result.error or "Unknown error")

                # Audio Size
                if result.audio_size_bytes > 0:
                    audio_sizes.append(result.audio_size_bytes)

                # Characters per Second
                text_length = len(result.text.replace(" ", ""))
                if result.synthesis_time_ms > 0:
                    cps = text_length / (result.synthesis_time_ms / 1000)
                    chars_per_second_list.append(cps)

            except Exception as e:
                self.errors.append(f"Error processing test case: {str(e)}")

        # 결과 집계
        summary = {
            "total_samples": len(data),
            "processed_samples": len(synthesis_times)
        }

        # Average Synthesis Time
        if synthesis_times:
            avg_time = sum(synthesis_times) / len(synthesis_times)
            self.results.append(self._create_metric_result(
                "avg_synthesis_time_ms", avg_time,
                details={"min": min(synthesis_times), "max": max(synthesis_times), "p95": sorted(synthesis_times)[int(len(synthesis_times) * 0.95)] if len(synthesis_times) > 1 else synthesis_times[0]}
            ))
            summary["avg_synthesis_time_ms"] = avg_time

        # Success Rate
        if data:
            success_rate = (success_count / len(data)) * 100
            self.results.append(self._create_metric_result(
                "success_rate", success_rate,
                details={"success": success_count, "total": len(data)}
            ))
            summary["success_rate"] = success_rate

        # Average Audio Size
        if audio_sizes:
            avg_size = sum(audio_sizes) / len(audio_sizes)
            self.results.append(self._create_metric_result(
                "avg_audio_size_bytes", avg_size,
                details={"min": min(audio_sizes), "max": max(audio_sizes)}
            ))
            summary["avg_audio_size_bytes"] = avg_size

        # Average Characters per Second
        if chars_per_second_list:
            avg_cps = sum(chars_per_second_list) / len(chars_per_second_list)
            self.results.append(self._create_metric_result(
                "avg_chars_per_second", avg_cps,
                details={"min": min(chars_per_second_list), "max": max(chars_per_second_list)}
            ))
            summary["avg_chars_per_second"] = avg_cps

        # Error Rate
        if data:
            error_rate = ((len(data) - success_count) / len(data)) * 100
            self.results.append(self._create_metric_result(
                "error_rate", error_rate
            ))
            summary["error_rate"] = error_rate

        # Error Details
        if errors:
            summary["error_details"] = errors[:10]  # 최대 10개만 저장

        return self._create_evaluation_result(start_time, summary)


def evaluate_tts_from_adapter(
    texts: List[str],
    tts_adapter: Any,
    voice: Optional[str] = None,
    format: str = "mp3"
) -> EvaluationResult:
    """
    TTS Adapter를 사용한 평가 헬퍼 함수

    Args:
        texts: 평가할 텍스트 리스트
        tts_adapter: TTSAdapter 인스턴스
        voice: 음성 (None이면 기본 음성)
        format: 오디오 포맷
    """
    import time

    eval_data = []
    for text in texts:
        test_case = TTSTestCase(
            text=text,
            voice=voice,
            format=format
        )

        # TTS 실행
        start_time = time.time()
        tts_result = tts_adapter.synthesize(text, voice=voice, format=format)
        end_time = time.time()

        synthesis_time_ms = (end_time - start_time) * 1000

        result = TTSMetricResult(
            audio=tts_result.audio,
            text=tts_result.text,
            voice=tts_result.voice,
            format=tts_result.format,
            synthesis_time_ms=synthesis_time_ms,
            audio_size_bytes=len(tts_result.audio),
            success=tts_result.error is None,
            error=tts_result.error
        )

        eval_data.append((test_case, result))

    metrics = TTSMetrics()
    return metrics.evaluate(eval_data)

