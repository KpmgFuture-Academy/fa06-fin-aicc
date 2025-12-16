# e2e_evaluation_pipeline/adapters/stt_adapter.py
"""STT(Speech-to-Text) 모듈과 E2E 평가 파이프라인 연동 어댑터.

실제 VITO STT 서비스를 호출하여 음성 인식 결과를
평가 가능한 형태로 변환합니다.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, BinaryIO
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class STTSegment:
    """음성 인식 세그먼트"""
    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None


@dataclass
class STTResult:
    """STT 결과"""
    text: str
    language: Optional[str] = None
    segments: List[STTSegment] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: Optional[str] = None


@dataclass
class STTEvaluationResult:
    """STT 평가 결과"""
    reference: str  # 정답 텍스트
    hypothesis: str  # 인식 결과
    wer: float  # Word Error Rate
    cer: float  # Character Error Rate
    accuracy: float  # 정확도 (1 - WER)
    match_rate: float  # 문자 매칭률


class STTAdapter:
    """STT 어댑터.

    E2E 평가 파이프라인에서 실제 VITO STT 서비스를 호출하고
    결과를 평가 가능한 형태로 변환합니다.
    """

    def __init__(self):
        self._stt_service = None
        self._initialized = False

    def _ensure_initialized(self):
        """STT 서비스 지연 초기화"""
        if self._initialized:
            return

        try:
            from app.services.voice.stt_service import AICCSTTService
            self._stt_service = AICCSTTService.get_instance()
            self._initialized = True
            logger.info("STT 서비스 초기화 완료")
        except Exception as e:
            logger.error(f"STT 서비스 초기화 실패: {e}")
            raise RuntimeError(f"STT 서비스 초기화 실패: {e}")

    def transcribe(
        self,
        audio: bytes | Path | BinaryIO,
        language: str = "ko",
        diarize: bool = False
    ) -> STTResult:
        """음성을 텍스트로 변환.

        Args:
            audio: 음성 데이터 (bytes, 파일 경로, 또는 스트림)
            language: 언어 코드 (기본값: "ko")
            diarize: 화자 분리 여부

        Returns:
            STTResult: 인식 결과
        """
        self._ensure_initialized()

        try:
            result = self._stt_service.transcribe(
                audio=audio,
                language=language,
                diarize=diarize
            )

            # 세그먼트 변환
            segments = [
                STTSegment(
                    text=seg.text,
                    start=seg.start,
                    end=seg.end,
                    confidence=seg.confidence,
                    speaker=seg.speaker
                )
                for seg in result.segments
            ]

            # 총 시간 계산
            duration = 0.0
            if segments and segments[-1].end:
                duration = segments[-1].end

            return STTResult(
                text=result.text,
                language=result.language,
                segments=segments,
                duration_seconds=duration
            )

        except Exception as e:
            logger.error(f"STT 변환 오류: {e}", exc_info=True)
            return STTResult(
                text="",
                error=str(e)
            )

    def transcribe_file(self, file_path: str | Path, **kwargs) -> STTResult:
        """파일에서 음성 인식.

        Args:
            file_path: 오디오 파일 경로
            **kwargs: transcribe()에 전달할 추가 인자

        Returns:
            STTResult: 인식 결과
        """
        return self.transcribe(Path(file_path), **kwargs)

    def transcribe_batch(
        self,
        audio_files: List[str | Path],
        **kwargs
    ) -> List[STTResult]:
        """배치 음성 인식.

        Args:
            audio_files: 오디오 파일 경로 리스트
            **kwargs: transcribe()에 전달할 추가 인자

        Returns:
            List[STTResult]: 인식 결과 리스트
        """
        results = []
        for audio_file in audio_files:
            result = self.transcribe_file(audio_file, **kwargs)
            results.append(result)
        return results

    def evaluate(
        self,
        reference: str,
        hypothesis: str
    ) -> STTEvaluationResult:
        """STT 결과 평가.

        Args:
            reference: 정답 텍스트
            hypothesis: 인식 결과

        Returns:
            STTEvaluationResult: 평가 결과
        """
        # WER (Word Error Rate) 계산
        wer = self._calculate_wer(reference, hypothesis)

        # CER (Character Error Rate) 계산
        cer = self._calculate_cer(reference, hypothesis)

        # 정확도
        accuracy = max(0.0, 1.0 - wer)

        # 문자 매칭률
        match_rate = self._calculate_match_rate(reference, hypothesis)

        return STTEvaluationResult(
            reference=reference,
            hypothesis=hypothesis,
            wer=wer,
            cer=cer,
            accuracy=accuracy,
            match_rate=match_rate
        )

    def evaluate_batch(
        self,
        pairs: List[tuple[str, str]]
    ) -> Dict[str, Any]:
        """배치 평가.

        Args:
            pairs: (정답, 인식결과) 튜플 리스트

        Returns:
            종합 평가 결과
        """
        if not pairs:
            return {
                "avg_wer": 0.0,
                "avg_cer": 0.0,
                "avg_accuracy": 0.0,
                "count": 0
            }

        total_wer = 0.0
        total_cer = 0.0
        total_accuracy = 0.0

        for ref, hyp in pairs:
            result = self.evaluate(ref, hyp)
            total_wer += result.wer
            total_cer += result.cer
            total_accuracy += result.accuracy

        count = len(pairs)
        return {
            "avg_wer": total_wer / count,
            "avg_cer": total_cer / count,
            "avg_accuracy": total_accuracy / count,
            "count": count
        }

    def _calculate_wer(self, reference: str, hypothesis: str) -> float:
        """Word Error Rate 계산 (Levenshtein distance 기반)"""
        ref_words = reference.split()
        hyp_words = hypothesis.split()

        if not ref_words:
            return 1.0 if hyp_words else 0.0

        # 동적 프로그래밍으로 편집 거리 계산
        d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]

        for i in range(len(ref_words) + 1):
            d[i][0] = i
        for j in range(len(hyp_words) + 1):
            d[0][j] = j

        for i in range(1, len(ref_words) + 1):
            for j in range(1, len(hyp_words) + 1):
                if ref_words[i-1] == hyp_words[j-1]:
                    d[i][j] = d[i-1][j-1]
                else:
                    d[i][j] = min(
                        d[i-1][j] + 1,    # 삭제
                        d[i][j-1] + 1,    # 삽입
                        d[i-1][j-1] + 1   # 대체
                    )

        return d[len(ref_words)][len(hyp_words)] / len(ref_words)

    def _calculate_cer(self, reference: str, hypothesis: str) -> float:
        """Character Error Rate 계산"""
        ref_chars = list(reference.replace(" ", ""))
        hyp_chars = list(hypothesis.replace(" ", ""))

        if not ref_chars:
            return 1.0 if hyp_chars else 0.0

        # 동적 프로그래밍으로 편집 거리 계산
        d = [[0] * (len(hyp_chars) + 1) for _ in range(len(ref_chars) + 1)]

        for i in range(len(ref_chars) + 1):
            d[i][0] = i
        for j in range(len(hyp_chars) + 1):
            d[0][j] = j

        for i in range(1, len(ref_chars) + 1):
            for j in range(1, len(hyp_chars) + 1):
                if ref_chars[i-1] == hyp_chars[j-1]:
                    d[i][j] = d[i-1][j-1]
                else:
                    d[i][j] = min(
                        d[i-1][j] + 1,
                        d[i][j-1] + 1,
                        d[i-1][j-1] + 1
                    )

        return d[len(ref_chars)][len(hyp_chars)] / len(ref_chars)

    def _calculate_match_rate(self, reference: str, hypothesis: str) -> float:
        """문자 매칭률 계산 (공백 제외)"""
        ref = reference.replace(" ", "")
        hyp = hypothesis.replace(" ", "")

        if not ref:
            return 1.0 if not hyp else 0.0

        # 일치하는 문자 수 (순서 무시)
        ref_chars = list(ref)
        hyp_chars = list(hyp)

        matches = 0
        for char in ref_chars:
            if char in hyp_chars:
                matches += 1
                hyp_chars.remove(char)

        return matches / len(ref)

    def get_token_info(self) -> Dict[str, Any]:
        """VITO API 토큰 정보 반환."""
        self._ensure_initialized()
        return self._stt_service.get_token_info()

    def is_available(self) -> bool:
        """STT 서비스 사용 가능 여부 확인."""
        try:
            self._ensure_initialized()
            return self._stt_service.is_token_valid()
        except Exception:
            return False
