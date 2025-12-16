"""
Lightweight VAD using the WebRTC algorithm.
(Modified for stability: Added flush method and tuned defaults)
"""

from __future__ import annotations

import webrtcvad

from app.services.vad.base import FrameResult, VADEngine


class WebRTCVADStream(VADEngine):
    """
    Streaming WebRTC VAD with simple start/stop aggregation.
    Expects 16-bit PCM mono. Frames are sliced to `frame_ms`.
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        frame_ms: int = 20,
        # 수정 1: 민감도 완화 (3->1 or 2->1). 1이 가장 관대함(잡음 허용).
        aggressiveness: int = 1,
        min_speech_ms: int = 100,  # 짧은 감탄사("아", "네")도 인식하도록 감소
        # 수정 2: 끊김 방지. 0.5초 침묵까지는 같은 문장으로 간주
        max_silence_ms: int = 500,
    ) -> None:
        if frame_ms not in (10, 20, 30):
            raise ValueError("frame_ms must be one of 10, 20, 30 for WebRTC VAD")
        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError("sample_rate must be one of 8000, 16000, 32000, 48000")

        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_bytes = int(sample_rate * frame_ms / 1000 * 2)  # 16-bit mono
        self.min_speech_ms = min_speech_ms
        self.max_silence_ms = max_silence_ms

        self.vad = webrtcvad.Vad(aggressiveness)

        self._buffer = bytearray()
        self._in_speech = False
        self._start_ms = 0
        self._last_speech_ms = 0
        self._silence_acc_ms = 0
        self._processed_ms = 0

    def reset(self) -> None:
        self._buffer.clear()
        self._in_speech = False
        self._start_ms = 0
        self._last_speech_ms = 0
        self._silence_acc_ms = 0
        self._processed_ms = 0

    def feed(self, audio: bytes) -> list[FrameResult]:
        self._buffer.extend(audio)
        results: list[FrameResult] = []

        while len(self._buffer) >= self.frame_bytes:
            frame = bytes(self._buffer[: self.frame_bytes])
            del self._buffer[: self.frame_bytes]

            speech = self.vad.is_speech(frame, self.sample_rate)
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
                                    score=None,
                                    raw={"engine": "webrtc"},
                                )
                            )
                        self._in_speech = False
                        self._silence_acc_ms = 0

        return results

    # 수정 3: flush 메소드 추가 (필수)
    def flush(self) -> list[FrameResult]:
        """
        오디오 스트림이 끝났을 때 호출.
        진행 중이던 발화가 있다면 강제로 반환함.
        """
        results: list[FrameResult] = []
        if self._in_speech:
            duration = self._last_speech_ms - self._start_ms
            # 최소 길이를 만족하면 반환
            if duration >= self.min_speech_ms:
                results.append(
                    FrameResult(
                        start_ms=self._start_ms,
                        end_ms=self._last_speech_ms,
                        is_speech=True,
                        score=None,
                        raw={"engine": "webrtc", "flushed": True},
                    )
                )
        self.reset()
        return results
