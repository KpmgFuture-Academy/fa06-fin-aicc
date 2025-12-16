"""
Hybrid VAD: WebRTC front filter + Silero confirmation.
"""

from __future__ import annotations

import webrtcvad

from app.services.vad.base import FrameResult, VADEngine
from app.services.vad.silero import SileroVADStream


class HybridVADStream(VADEngine):
    """
    Runs WebRTC first for speed, then Silero to confirm/refine.
    Mode:
      - "and": require both WebRTC speech and Silero prob >= threshold
      - "or": accept speech if either engine says speech
      - "silero_only": use Silero only (more accurate, slightly slower)

    Note: WebRTC supports 10/20/30ms frames, but Silero requires minimum 512 samples
    (~32ms at 16kHz). We use 30ms for WebRTC (480 samples) and accumulate frames
    for Silero scoring to meet the minimum requirement.
    """

    # Silero 정확한 샘플 수 (16kHz 기준, 512 샘플만 허용)
    SILERO_EXACT_SAMPLES = 512

    def __init__(
        self,
        silero: SileroVADStream,
        *,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        aggressiveness: int = 2,
        min_speech_ms: int = 150,
        max_silence_ms: int = 300,
        mode: str = "and",
    ) -> None:
        if frame_ms not in (10, 20, 30):
            raise ValueError("frame_ms must be one of 10, 20, 30 for WebRTC VAD")
        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError("sample_rate must be one of 8000, 16000, 32000, 48000")
        if mode not in ("and", "or", "silero_only"):
            raise ValueError("mode must be 'and', 'or', or 'silero_only'")

        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_bytes = int(sample_rate * frame_ms / 1000 * 2)
        self.min_speech_ms = min_speech_ms
        self.max_silence_ms = max_silence_ms
        self.mode = mode

        self.vad = webrtcvad.Vad(aggressiveness)
        self.silero = silero
        self.silero_threshold = silero.threshold

        self._buffer = bytearray()
        self._silero_buffer = bytearray()  # Silero용 누적 버퍼
        self._in_speech = False
        self._start_ms = 0
        self._last_speech_ms = 0
        self._silence_acc_ms = 0
        self._processed_ms = 0

    def reset(self) -> None:
        self._buffer.clear()
        self._silero_buffer.clear()
        self._in_speech = False
        self._start_ms = 0
        self._last_speech_ms = 0
        self._silence_acc_ms = 0
        self._processed_ms = 0

    def _get_silero_score(self, frame: bytes) -> float | None:
        """
        Silero 점수를 계산합니다.
        Silero는 정확히 512 샘플만 허용하므로, 프레임을 누적하여 512 샘플이 되면 점수를 계산합니다.
        """
        self._silero_buffer.extend(frame)

        # 정확히 512 샘플 필요 (16-bit = 2 bytes per sample)
        silero_exact_bytes = self.SILERO_EXACT_SAMPLES * 2  # 1024 bytes
        if len(self._silero_buffer) >= silero_exact_bytes:
            # 정확히 512 샘플만 추출하여 Silero에 전달
            silero_frame = bytes(self._silero_buffer[:silero_exact_bytes])
            # 사용한 바이트만 제거 (나머지는 다음 계산에 사용)
            del self._silero_buffer[:silero_exact_bytes]
            return self.silero.score_frame(silero_frame)

        return None

    def feed(self, audio: bytes) -> list[FrameResult]:
        self._buffer.extend(audio)
        results: list[FrameResult] = []

        while len(self._buffer) >= self.frame_bytes:
            frame = bytes(self._buffer[: self.frame_bytes])
            del self._buffer[: self.frame_bytes]

            w_speech = self.vad.is_speech(frame, self.sample_rate)
            s_prob = None

            # Silero 점수 계산 조건:
            # - silero_only 모드: 항상
            # - or 모드: 항상
            # - and 모드: WebRTC가 음성이거나, 이미 음성 중일 때 (침묵 감지용)
            if self.mode == "silero_only" or self.mode == "or" or w_speech or self._in_speech:
                s_prob = self._get_silero_score(frame)

            if self.mode == "silero_only":
                # Silero만 사용 (더 정확한 음성 감지)
                if s_prob is None:
                    # Silero 버퍼 누적 중 - WebRTC를 백업으로 사용 (음성 시작 감지용)
                    speech = w_speech if not self._in_speech else self._in_speech
                else:
                    speech = s_prob >= self.silero_threshold
            elif self.mode == "and":
                # 음성 시작: WebRTC와 Silero 모두 음성이어야 함
                # 음성 종료: Silero가 침묵이면 종료 (WebRTC 노이즈 무시)
                if s_prob is None:
                    speech = w_speech  # WebRTC 결과만 사용
                elif self._in_speech:
                    # 이미 음성 중: Silero 기반으로 침묵 감지 (더 정확)
                    speech = s_prob >= self.silero_threshold
                else:
                    # 음성 시작 감지: 둘 다 음성이어야 함
                    speech = w_speech and s_prob >= self.silero_threshold
            else:  # "or"
                if s_prob is None:
                    speech = w_speech
                else:
                    speech = w_speech or s_prob >= self.silero_threshold

            frame_start_ms = self._processed_ms
            frame_end_ms = self._processed_ms + self.frame_ms
            self._processed_ms = frame_end_ms

            if speech:
                if not self._in_speech:
                    self._start_ms = frame_start_ms
                self._in_speech = True
                self._last_speech_ms = frame_end_ms
                self._silence_acc_ms = 0
            else:
                if self._in_speech:
                    self._silence_acc_ms += self.frame_ms
                    if self._silence_acc_ms >= self.max_silence_ms:
                        duration = self._last_speech_ms - self._start_ms
                        if duration >= self.min_speech_ms:
                            results.append(
                                FrameResult(
                                    start_ms=self._start_ms,
                                    end_ms=self._last_speech_ms,
                                    is_speech=True,
                                    score=s_prob,
                                    raw={
                                        "engine": "hybrid",
                                        "webrtc": w_speech,
                                        "silero_prob": s_prob,
                                        "mode": self.mode,
                                    },
                                )
                            )
                        self._in_speech = False
                        self._silence_acc_ms = 0

        return results

