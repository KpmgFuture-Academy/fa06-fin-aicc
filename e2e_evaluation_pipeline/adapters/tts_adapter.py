# e2e_evaluation_pipeline/adapters/tts_adapter.py
"""TTS(Text-to-Speech) 모듈과 E2E 평가 파이프라인 연동 어댑터.

실제 Google TTS 서비스를 호출하여 음성 합성 결과를
평가 가능한 형태로 변환합니다.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, BinaryIO
from dataclasses import dataclass
from pathlib import Path
import time

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    """TTS 결과"""
    audio: bytes
    text: str
    voice: str
    format: str
    mime_type: str
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class TTSEvaluationResult:
    """TTS 평가 결과"""
    text: str
    audio_size_bytes: int
    synthesis_time_ms: float
    chars_per_second: float
    success: bool
    error: Optional[str] = None


class TTSAdapter:
    """TTS 어댑터.

    E2E 평가 파이프라인에서 실제 Google TTS 서비스를 호출하고
    결과를 평가 가능한 형태로 변환합니다.
    """

    def __init__(self, use_google: bool = True):
        """
        Args:
            use_google: Google TTS 사용 여부 (False면 OpenAI TTS)
        """
        self._tts_service = None
        self._initialized = False
        self._use_google = use_google

    def _ensure_initialized(self):
        """TTS 서비스 지연 초기화"""
        if self._initialized:
            return

        try:
            if self._use_google:
                from app.services.voice.tts_service_google import AICCGoogleTTSService
                self._tts_service = AICCGoogleTTSService.get_instance()
                logger.info("Google TTS 서비스 초기화 완료")
            else:
                from app.services.voice.tts_service import AICCTTSService
                self._tts_service = AICCTTSService.get_instance()
                logger.info("OpenAI TTS 서비스 초기화 완료")

            self._initialized = True
        except Exception as e:
            logger.error(f"TTS 서비스 초기화 실패: {e}")
            raise RuntimeError(f"TTS 서비스 초기화 실패: {e}")

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        format: str = "mp3"
    ) -> TTSResult:
        """텍스트를 음성으로 변환.

        Args:
            text: 변환할 텍스트
            voice: 음성 (None이면 기본 음성)
            format: 오디오 포맷 (mp3, wav, ogg)

        Returns:
            TTSResult: 합성 결과
        """
        self._ensure_initialized()

        if not text or not text.strip():
            return TTSResult(
                audio=b"",
                text=text,
                voice=voice or "",
                format=format,
                mime_type="",
                error="텍스트가 비어있습니다"
            )

        try:
            result = self._tts_service.synthesize_full(
                text=text,
                voice=voice,
                format=format
            )

            return TTSResult(
                audio=result.audio,
                text=result.text,
                voice=result.voice,
                format=result.format,
                mime_type=result.mime_type
            )

        except Exception as e:
            logger.error(f"TTS 합성 오류: {e}", exc_info=True)
            return TTSResult(
                audio=b"",
                text=text,
                voice=voice or "",
                format=format,
                mime_type="",
                error=str(e)
            )

    def synthesize_to_file(
        self,
        text: str,
        file_path: str | Path,
        voice: Optional[str] = None,
        format: str = "mp3"
    ) -> Path:
        """텍스트를 음성 파일로 저장.

        Args:
            text: 변환할 텍스트
            file_path: 저장할 파일 경로
            voice: 음성
            format: 오디오 포맷

        Returns:
            저장된 파일 경로
        """
        self._ensure_initialized()
        return self._tts_service.synthesize_to_file(
            text=text,
            path=file_path,
            voice=voice,
            format=format
        )

    def synthesize_batch(
        self,
        texts: List[str],
        voice: Optional[str] = None,
        format: str = "mp3"
    ) -> List[TTSResult]:
        """배치 음성 합성.

        Args:
            texts: 텍스트 리스트
            voice: 음성
            format: 오디오 포맷

        Returns:
            List[TTSResult]: 합성 결과 리스트
        """
        results = []
        for text in texts:
            result = self.synthesize(text, voice=voice, format=format)
            results.append(result)
        return results

    def evaluate(
        self,
        text: str,
        voice: Optional[str] = None,
        format: str = "mp3"
    ) -> TTSEvaluationResult:
        """TTS 성능 평가.

        Args:
            text: 변환할 텍스트
            voice: 음성
            format: 오디오 포맷

        Returns:
            TTSEvaluationResult: 평가 결과
        """
        start_time = time.time()
        result = self.synthesize(text, voice=voice, format=format)
        end_time = time.time()

        synthesis_time_ms = (end_time - start_time) * 1000
        text_length = len(text.replace(" ", ""))
        chars_per_second = text_length / (synthesis_time_ms / 1000) if synthesis_time_ms > 0 else 0

        return TTSEvaluationResult(
            text=text,
            audio_size_bytes=len(result.audio),
            synthesis_time_ms=synthesis_time_ms,
            chars_per_second=chars_per_second,
            success=result.error is None,
            error=result.error
        )

    def evaluate_batch(
        self,
        texts: List[str],
        voice: Optional[str] = None,
        format: str = "mp3"
    ) -> Dict[str, Any]:
        """배치 평가.

        Args:
            texts: 텍스트 리스트
            voice: 음성
            format: 오디오 포맷

        Returns:
            종합 평가 결과
        """
        if not texts:
            return {
                "avg_synthesis_time_ms": 0.0,
                "avg_audio_size_bytes": 0,
                "avg_chars_per_second": 0.0,
                "success_rate": 0.0,
                "count": 0
            }

        total_time = 0.0
        total_size = 0
        total_cps = 0.0
        success_count = 0

        for text in texts:
            result = self.evaluate(text, voice=voice, format=format)
            total_time += result.synthesis_time_ms
            total_size += result.audio_size_bytes
            total_cps += result.chars_per_second
            if result.success:
                success_count += 1

        count = len(texts)
        return {
            "avg_synthesis_time_ms": total_time / count,
            "avg_audio_size_bytes": total_size / count,
            "avg_chars_per_second": total_cps / count,
            "success_rate": success_count / count,
            "count": count
        }

    def get_available_voices(self) -> List[str]:
        """사용 가능한 음성 목록 반환."""
        # Google TTS 한국어 음성 목록
        if self._use_google:
            return [
                "ko-KR-Neural2-A",  # 여성
                "ko-KR-Neural2-B",  # 여성
                "ko-KR-Neural2-C",  # 남성
                "ko-KR-Standard-A",
                "ko-KR-Standard-B",
                "ko-KR-Standard-C",
                "ko-KR-Standard-D",
                "ko-KR-Wavenet-A",
                "ko-KR-Wavenet-B",
                "ko-KR-Wavenet-C",
                "ko-KR-Wavenet-D",
            ]
        else:
            # OpenAI TTS 음성 목록
            return [
                "alloy",
                "echo",
                "fable",
                "onyx",
                "nova",
                "shimmer"
            ]

    def get_default_voice(self) -> str:
        """기본 음성 반환."""
        self._ensure_initialized()
        return self._tts_service.default_voice

    def get_supported_formats(self) -> List[str]:
        """지원 포맷 목록 반환."""
        if self._use_google:
            return ["mp3", "wav", "ogg", "opus"]
        else:
            return ["mp3", "opus", "aac", "flac"]

    def is_available(self) -> bool:
        """TTS 서비스 사용 가능 여부 확인."""
        try:
            self._ensure_initialized()
            return True
        except Exception:
            return False

    def estimate_duration(self, text: str, chars_per_second: float = 5.0) -> float:
        """예상 음성 길이 계산 (초).

        Args:
            text: 텍스트
            chars_per_second: 초당 문자 수 (한국어 기준 약 5자/초)

        Returns:
            예상 시간 (초)
        """
        text_length = len(text.replace(" ", ""))
        return text_length / chars_per_second
