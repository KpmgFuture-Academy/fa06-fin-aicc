"""
Silero VAD Service
음성 활동 감지를 위한 Silero VAD 모델 서비스

특징:
- 딥러닝 기반 정확한 음성/비음성 구분
- 노이즈, 키보드 소리 등 비음성 필터링
- 실시간 스트리밍 처리 지원
"""

import torch
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SileroVADService:
    """Silero VAD 모델을 사용한 음성 활동 감지 서비스"""

    def __init__(
        self,
        threshold: float = 0.5,
        sample_rate: int = 16000,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 2000,
    ):
        """
        Args:
            threshold: 음성 감지 임계값 (0.0 ~ 1.0, 기본 0.5)
            sample_rate: 오디오 샘플레이트 (8000 또는 16000)
            min_speech_duration_ms: 최소 음성 지속 시간 (ms)
            min_silence_duration_ms: 최소 침묵 지속 시간 (ms)
        """
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms

        # 모델 로드
        self.model = None
        self.utils = None
        self._load_model()

        # 상태 관리
        self.is_speaking = False
        self.speech_start_time: Optional[float] = None
        self.silence_start_time: Optional[float] = None
        self.accumulated_audio: list = []

        logger.info(f"SileroVAD 초기화 완료 (threshold={threshold}, sample_rate={sample_rate})")

    def _load_model(self):
        """Silero VAD 모델 로드"""
        try:
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            self.model.eval()
            logger.info("Silero VAD 모델 로드 완료")
        except Exception as e:
            logger.error(f"Silero VAD 모델 로드 실패: {e}")
            raise

    def reset_state(self):
        """VAD 상태 초기화"""
        self.is_speaking = False
        self.speech_start_time = None
        self.silence_start_time = None
        self.accumulated_audio = []
        # 모델 내부 상태도 리셋
        if self.model is not None:
            self.model.reset_states()

    def process_chunk(self, audio_chunk: bytes) -> dict:
        """
        오디오 청크 처리 및 VAD 결과 반환

        Args:
            audio_chunk: INT16 PCM 오디오 데이터 (bytes)

        Returns:
            dict: {
                'is_speech': bool,          # 현재 청크가 음성인지
                'speech_prob': float,       # 음성 확률 (0.0 ~ 1.0)
                'state_changed': bool,      # 상태 변경 여부 (음성 시작/끝)
                'event': str | None,        # 'speech_start', 'speech_end', None
            }
        """
        try:
            # bytes -> numpy array (INT16)
            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)

            # INT16 -> Float32 (-1.0 ~ 1.0)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # Silero VAD는 정확히 512 샘플(16kHz) 또는 256 샘플(8kHz)만 처리 가능
            # 청크를 512 샘플 단위로 나눠서 처리하고 평균 확률 계산
            chunk_size = 512 if self.sample_rate == 16000 else 256
            speech_probs = []

            for i in range(0, len(audio_float32), chunk_size):
                chunk = audio_float32[i:i + chunk_size]
                if len(chunk) == chunk_size:
                    audio_tensor = torch.from_numpy(chunk)
                    prob = self.model(audio_tensor, self.sample_rate).item()
                    speech_probs.append(prob)

            # 평균 확률 계산 (청크가 없으면 0)
            speech_prob = sum(speech_probs) / len(speech_probs) if speech_probs else 0.0

            is_speech = speech_prob >= self.threshold

            # 상태 변경 감지
            state_changed = False
            event = None

            if is_speech and not self.is_speaking:
                # 음성 시작
                self.is_speaking = True
                self.silence_start_time = None
                state_changed = True
                event = 'speech_start'
                logger.debug(f"음성 시작 감지 (prob={speech_prob:.3f})")

            elif not is_speech and self.is_speaking:
                # 침묵 시작 (아직 음성 끝은 아님)
                import time
                current_time = time.time() * 1000  # ms

                if self.silence_start_time is None:
                    self.silence_start_time = current_time
                elif current_time - self.silence_start_time >= self.min_silence_duration_ms:
                    # 충분한 침묵 후 음성 종료
                    self.is_speaking = False
                    state_changed = True
                    event = 'speech_end'
                    logger.debug(f"음성 종료 감지 (silence={current_time - self.silence_start_time:.0f}ms)")

            elif is_speech and self.is_speaking:
                # 계속 말하는 중 - 침묵 타이머 리셋
                self.silence_start_time = None

            return {
                'is_speech': is_speech,
                'speech_prob': speech_prob,
                'state_changed': state_changed,
                'event': event,
            }

        except Exception as e:
            logger.error(f"VAD 처리 오류: {e}")
            return {
                'is_speech': False,
                'speech_prob': 0.0,
                'state_changed': False,
                'event': None,
            }

    def get_speech_probability(self, audio_chunk: bytes) -> float:
        """
        단순히 음성 확률만 반환 (상태 변경 없음)

        Args:
            audio_chunk: INT16 PCM 오디오 데이터 (bytes)

        Returns:
            float: 음성 확률 (0.0 ~ 1.0)
        """
        try:
            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            chunk_size = 512 if self.sample_rate == 16000 else 256
            speech_probs = []

            for i in range(0, len(audio_float32), chunk_size):
                chunk = audio_float32[i:i + chunk_size]
                if len(chunk) == chunk_size:
                    audio_tensor = torch.from_numpy(chunk)
                    with torch.no_grad():
                        prob = self.model(audio_tensor, self.sample_rate).item()
                    speech_probs.append(prob)

            return sum(speech_probs) / len(speech_probs) if speech_probs else 0.0

        except Exception as e:
            logger.error(f"음성 확률 계산 오류: {e}")
            return 0.0


# 싱글톤 인스턴스
_vad_instance: Optional[SileroVADService] = None


def get_vad_service(
    threshold: float = 0.3,
    sample_rate: int = 16000,
    min_silence_duration_ms: int = 2000,
) -> SileroVADService:
    """VAD 서비스 싱글톤 인스턴스 반환"""
    global _vad_instance
    if _vad_instance is None:
        _vad_instance = SileroVADService(
            threshold=threshold,
            sample_rate=sample_rate,
            min_silence_duration_ms=min_silence_duration_ms,
        )
    else:
        # 기존 인스턴스의 threshold 업데이트
        _vad_instance.threshold = threshold
    return _vad_instance
