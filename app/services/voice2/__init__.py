# fa06-fin-aicc/app/services/voice2/__init__.py
from . import stt2
from .stt2 import (
    authenticate,
    ReturnZeroSTTEngine,
    VitoSpeechToTextService,
    VitoTranscriptionResult,
    VitoTranscriptionSegment,
    VitoSTTEngine,
    VitoSTTError,
)

__all__ = [
    "stt2",
    "authenticate",
    "ReturnZeroSTTEngine",
    "VitoSpeechToTextService",
    "VitoTranscriptionResult",
    "VitoTranscriptionSegment",
    "VitoSTTEngine",
    "VitoSTTError",
]
