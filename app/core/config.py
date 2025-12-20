"""애플리케이션 설정 모듈
.env 파일에서 설정을 로드합니다.
"""

from typing import Optional
import os
from pathlib import Path
from dotenv import load_dotenv
try:
    from pydantic_settings import BaseSettings  # type: ignore
except ModuleNotFoundError:
    # pydantic_settings 미설치 환경을 위한 간단 대체
    class BaseSettings:  # noqa: D401
        """Lightweight fallback when pydantic_settings is unavailable."""
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

# .env 파일 경로
env_path = Path(__file__).parent.parent.parent / ".env"

# 환경 변수에 이미 들어있는 OPENAI_API_KEY를 잠시 빼둠(오염 방지)
original_env_key = os.environ.pop("OPENAI_API_KEY", None)

# .env 파일에서 값을 직접 읽어 환경 변수에 적용
env_values = {}
if env_path.exists():
    from dotenv import dotenv_values

    env_values = dotenv_values(env_path)
    for key, value in env_values.items():
        if value:
            os.environ[key] = value
else:
    load_dotenv(override=True)


class Settings(BaseSettings):
    """애플리케이션 설정 (.env 기반)"""

    # 애플리케이션 기본
    app_name: str = "Bank AICC Dev Server"
    debug: bool = False

    # 데이터베이스
    database_url: str = "mysql+pymysql://root:password@localhost:3306/aicc_db?charset=utf8mb4"

    # OpenAI
    openai_api_key: Optional[str] = None

    # ===== STT/TTS 설정 =====
    # VITO STT (Return Zero)
    vito_client_id: Optional[str] = None
    vito_client_secret: Optional[str] = None
    vito_stt_timeout: int = 60

    # OpenAI TTS
    tts_voice: str = "alloy"
    tts_model: str = "tts-1"
    tts_timeout: int = 30

    # ===== LLM 설정 =====
    # LM Studio
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "openai/gpt-oss-20b"
    use_lm_studio: bool = False
    llm_timeout: int = 60

    # 벡터 DB (ChromaDB)
    vector_db_path: str = "./chroma_db"
    embedding_model: str = "jhgan/ko-sroberta-multitask"
    collection_name: str = "financial_documents"
    similarity_threshold: float = 0.2
    enable_query_expansion: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"  # .env에 정의된 추가 키(Hume, Google 등)를 허용


# settings 인스턴스
settings = Settings()

# 원래 OPENAI_API_KEY가 있었다면 복원
if original_env_key:
    os.environ["OPENAI_API_KEY"] = original_env_key
