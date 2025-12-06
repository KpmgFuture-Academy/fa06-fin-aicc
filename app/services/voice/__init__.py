"""음성 서비스 모듈 (STT/TTS)

STT: VITO (Return Zero) - 한국어 음성 인식
TTS: OpenAI TTS-1 - 텍스트 음성 합성
"""

from .stt_service import AICCSTTService, STTResult, STTError
from .tts_service import AICCTTSService, TTSError

__all__ = [
    "AICCSTTService",
    "STTResult",
    "STTError",
    "AICCTTSService", 
    "TTSError",
]

