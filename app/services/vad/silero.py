"""
Silero VAD wrapper for streaming PCM16 mono audio.
"""

from __future__ import annotations

import os
from typing import Callable

try:
    import torch
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError("torch is required for SileroVADStream") from exc

from app.services.vad.base import FrameResult, VADEngine


class SileroVADStream(VADEngine):
    """
    Streaming VAD using a Silero model (TorchScript).
    Supports: (1) torch.hub.load (default), (2) local jit file via SILERO_VAD_MODEL_PATH, (3) model injection.
    """

    # Silero VAD 최소 샘플 수 (16kHz 기준 약 32ms = 512 샘플)
    MIN_SAMPLES = 512

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        frame_ms: int = 40,
        threshold: float = 0.5,
        min_speech_ms: int = 150,
        max_silence_ms: int = 400,
        model_path: str | None = None,
        model: Callable | None = None,
        device: str = "cpu",
        use_hub: bool = True,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_bytes = int(sample_rate * frame_ms / 1000 * 2)  # 16-bit mono
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.max_silence_ms = max_silence_ms
        self.device = torch.device(device)

        path = model_path or os.getenv("SILERO_VAD_MODEL_PATH")

        if model is not None:
            # 모델 직접 주입
            self.model = model
        elif path:
            # 로컬 JIT 파일 사용
            self.model = torch.jit.load(path, map_location=self.device)
        elif use_hub:
            # torch.hub에서 Silero VAD 다운로드 (기본값)
            self.model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
        else:
            raise RuntimeError("Provide a Silero VAD model via `model`, `model_path`, or set use_hub=True")

        self.model.eval()

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

    def _score_frame(self, frame: bytes) -> float:
        """
        Run a single frame through the Silero model and return speech probability.
        Silero expects float32 waveform in range [-1, 1] with shape [batch, samples].

        Note: Silero VAD requires EXACTLY 512 samples for 16kHz (or 256 for 8kHz).
        """
        # 정확한 샘플 수 검증 (16kHz = 512 샘플, 8kHz = 256 샘플)
        num_samples = len(frame) // 2  # 16-bit = 2 bytes per sample
        expected_samples = self.MIN_SAMPLES  # 512 for 16kHz

        if num_samples != expected_samples:
            # 샘플 수가 정확하지 않으면 기본값 반환 (음성 아님으로 처리)
            return 0.0

        with torch.no_grad():
            waveform = torch.frombuffer(frame, dtype=torch.int16).to(self.device).float()
            waveform = waveform / 32768.0
            prob = self.model(waveform.unsqueeze(0), self.sample_rate)[0]  # type: ignore[index]
            return float(prob.item())

    def score_frame(self, frame: bytes) -> float:
        """Public wrapper around the per-frame scoring helper."""
        return self._score_frame(frame)

    def feed(self, audio: bytes) -> list[FrameResult]:
        self._buffer.extend(audio)
        results: list[FrameResult] = []

        while len(self._buffer) >= self.frame_bytes:
            frame = bytes(self._buffer[: self.frame_bytes])
            del self._buffer[: self.frame_bytes]

            prob = self._score_frame(frame)
            speech = prob >= self.threshold

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
                                    score=prob,
                                    raw={"engine": "silero"},
                                )
                            )
                        self._in_speech = False
                        self._silence_acc_ms = 0

        return results
