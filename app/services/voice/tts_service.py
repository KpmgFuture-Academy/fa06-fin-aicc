"""OpenAI TTS 서비스 - AICC 파이프라인용

OpenAI TTS-1 API를 사용한 텍스트 음성 합성 서비스.
싱글톤 패턴 적용.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI TTS API 엔드포인트
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"

# 지원하는 음성 목록
SUPPORTED_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}

# 지원하는 출력 포맷
SUPPORTED_FORMATS = {"mp3", "opus", "aac", "flac", "wav", "pcm"}


class TTSError(RuntimeError):
    """TTS 처리 중 발생하는 예외"""
    pass


@dataclass
class TTSResult:
    """TTS 결과"""
    audio: bytes
    voice: str
    format: str
    text: str
    mime_type: str


class AICCTTSService:
    """AICC용 OpenAI TTS 서비스 (싱글톤)
    
    특징:
    - 다양한 음성 지원 (alloy, echo, fable, onyx, nova, shimmer)
    - 여러 출력 포맷 지원 (mp3, opus, aac, flac, wav, pcm)
    - 텍스트 길이 제한 검증 (4096자)
    
    사용 예:
        tts = AICCTTSService.get_instance()
        audio_bytes = tts.synthesize("안녕하세요")
    """
    
    _instance: Optional["AICCTTSService"] = None
    
    # 텍스트 최대 길이 (OpenAI 제한)
    MAX_TEXT_LENGTH = 4096
    
    def __init__(self):
        """직접 생성하지 말고 get_instance() 사용"""
        if not settings.openai_api_key:
            raise TTSError(
                "OpenAI API 키가 설정되지 않았습니다. "
                ".env 파일에 OPENAI_API_KEY를 설정하세요."
            )
        
        self._api_key = settings.openai_api_key
        self._model = settings.tts_model
        self._default_voice = settings.tts_voice
        self._timeout = settings.tts_timeout
        self._session = requests.Session()
        
        logger.info(f"OpenAI TTS 초기화 완료 (model: {self._model}, voice: {self._default_voice})")
    
    @classmethod
    def get_instance(cls) -> "AICCTTSService":
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """인스턴스 리셋 (테스트용)"""
        cls._instance = None
    
    def synthesize(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> bytes:
        """텍스트를 음성으로 변환
        
        Args:
            text: 변환할 텍스트 (최대 4096자)
            voice: 음성 종류 (기본값: 설정된 tts_voice)
            format: 출력 포맷 (mp3, opus, aac, flac, wav, pcm)
            
        Returns:
            bytes: 음성 데이터
            
        Raises:
            TTSError: 변환 실패 시
        """
        # 입력 검증
        if not text or not text.strip():
            raise TTSError("텍스트가 비어있습니다.")
        
        if len(text) > self.MAX_TEXT_LENGTH:
            raise TTSError(f"텍스트가 너무 깁니다. (최대 {self.MAX_TEXT_LENGTH}자, 현재 {len(text)}자)")
        
        voice = voice or self._default_voice
        if voice not in SUPPORTED_VOICES:
            raise TTSError(f"지원하지 않는 음성: {voice}. 지원: {SUPPORTED_VOICES}")
        
        if format not in SUPPORTED_FORMATS:
            raise TTSError(f"지원하지 않는 포맷: {format}. 지원: {SUPPORTED_FORMATS}")
        
        # API 요청
        payload = {
            "model": self._model,
            "input": text,
            "voice": voice,
            "response_format": format,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            logger.debug(f"OpenAI TTS 요청 시작 (텍스트 길이: {len(text)}자, voice: {voice})")
            
            response = self._session.post(
                OPENAI_TTS_URL,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            
        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            logger.error(f"OpenAI TTS 요청 실패: {detail}")
            raise TTSError(f"OpenAI TTS 요청 실패: {detail}") from exc
        
        audio_bytes = response.content
        logger.info(f"OpenAI TTS 완료 (크기: {len(audio_bytes)} bytes)")
        
        return audio_bytes
    
    def synthesize_full(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> TTSResult:
        """텍스트를 음성으로 변환 (상세 결과 반환)
        
        Returns:
            TTSResult: 음성 데이터 및 메타 정보
        """
        voice = voice or self._default_voice
        audio_bytes = self.synthesize(text, voice=voice, format=format)
        
        # MIME 타입 매핑
        mime_types = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm",
        }
        
        return TTSResult(
            audio=audio_bytes,
            voice=voice,
            format=format,
            text=text,
            mime_type=mime_types.get(format, f"audio/{format}"),
        )
    
    def synthesize_to_file(
        self,
        text: str,
        path: str | Path,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> Path:
        """텍스트를 음성으로 변환하여 파일로 저장
        
        Args:
            text: 변환할 텍스트
            path: 저장할 파일 경로
            voice: 음성 종류
            format: 출력 포맷
            
        Returns:
            Path: 저장된 파일 경로
        """
        audio_bytes = self.synthesize(text, voice=voice, format=format)
        
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(audio_bytes)
        
        logger.info(f"TTS 결과 저장: {file_path}")
        return file_path
    
    def synthesize_to_stream(
        self,
        text: str,
        stream: BinaryIO,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> int:
        """텍스트를 음성으로 변환하여 스트림에 쓰기
        
        Returns:
            int: 쓴 바이트 수
        """
        audio_bytes = self.synthesize(text, voice=voice, format=format)
        stream.write(audio_bytes)
        return len(audio_bytes)
    
    def synthesize_chunked(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
        max_chunk_length: int = 1000,
    ) -> list[bytes]:
        """긴 텍스트를 청크로 나누어 음성 변환
        
        긴 텍스트를 문장 단위로 나누어 여러 음성 파일로 변환합니다.
        실시간 스트리밍에 유용합니다.
        
        Args:
            text: 변환할 텍스트
            voice: 음성 종류
            format: 출력 포맷
            max_chunk_length: 청크 최대 길이 (기본값: 1000자)
            
        Returns:
            list[bytes]: 청크별 음성 데이터 리스트
        """
        chunks = self._split_text(text, max_chunk_length)
        results: list[bytes] = []
        
        for i, chunk in enumerate(chunks):
            logger.debug(f"TTS 청크 {i+1}/{len(chunks)} 처리 중...")
            audio = self.synthesize(chunk, voice=voice, format=format)
            results.append(audio)
        
        return results
    
    @staticmethod
    def _split_text(text: str, max_length: int) -> list[str]:
        """텍스트를 문장 단위로 분할
        
        문장 종결 부호를 기준으로 분할하되, max_length를 초과하지 않도록 합니다.
        """
        # 문장 종결 부호
        sentence_endings = (".", "!", "?", "。", "！", "？")
        
        chunks: list[str] = []
        current_chunk = ""
        
        sentences = []
        current_sentence = ""
        
        for char in text:
            current_sentence += char
            if char in sentence_endings:
                sentences.append(current_sentence.strip())
                current_sentence = ""
        
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_length:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                
                # 문장 자체가 max_length를 초과하면 강제 분할
                if len(sentence) > max_length:
                    for i in range(0, len(sentence), max_length):
                        chunks.append(sentence[i:i + max_length])
                    current_chunk = ""
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else [text]
    
    @property
    def default_voice(self) -> str:
        """기본 음성 반환"""
        return self._default_voice
    
    @property
    def model(self) -> str:
        """사용 중인 모델 반환"""
        return self._model

