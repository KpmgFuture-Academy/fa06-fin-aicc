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
    """

    def __init__(
        self,
        silero: SileroVADStream,
        *,
        sample_rate: int = 16000,
        frame_ms: int = 20,
        aggressiveness: int = 2,
        min_speech_ms: int = 150,
        max_silence_ms: int = 300,
        mode: str = "and",
    ) -> None:
        if frame_ms not in (10, 20, 30):
            raise ValueError("frame_ms must be one of 10, 20, 30 for WebRTC VAD")
        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError("sample_rate must be one of 8000, 16000, 32000, 48000")
        if mode not in ("and", "or"):
            raise ValueError("mode must be 'and' or 'or'")

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

            w_speech = self.vad.is_speech(frame, self.sample_rate)
            s_prob = None
            if w_speech or self.mode == "or":
                s_prob = self.silero.score_frame(frame)

            if self.mode == "and":
                speech = w_speech and (s_prob is not None and s_prob >= self.silero_threshold)
            else:  # "or"
                speech = w_speech or (s_prob is not None and s_prob >= self.silero_threshold)

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

