"""
Common types and helpers for VAD engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class FrameResult:
    """Per-frame or aggregated VAD decision."""

    start_ms: int
    end_ms: int
    is_speech: bool
    score: float | None = None
    raw: object | None = None


class VADEngine(Protocol):
    """
    Streaming VAD interface.
    Call `feed` repeatedly with PCM16 mono bytes; it returns any
    finalized speech segments detected in that chunk.
    """

    def feed(self, audio: bytes) -> list[FrameResult]: ...

    def reset(self) -> None: ...

