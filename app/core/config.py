"""애플리케이션 설정
.env 파일에서만 설정을 로드합니다. 환경 변수는 무시합니다.
"""

from typing import Optional
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


# .env 파일 경로
env_path = Path(__file__).parent.parent.parent / ".env"

# 환경 변수에서 OPENAI_API_KEY를 임시로 제거 (나중에 복원)
original_env_key = os.environ.pop("OPENAI_API_KEY", None)

# .env 파일에서 직접 읽기
env_values = {}
if env_path.exists():
    from dotenv import dotenv_values
    env_values = dotenv_values(env_path)
    # .env 파일의 값을 환경 변수에 설정 (다른 설정들도 읽을 수 있도록)
    for key, value in env_values.items():
        if value:  # 빈 값이 아닌 경우만
            os.environ[key] = value
else:
    # .env 파일이 없으면 기본 로드 시도
    load_dotenv(override=True)


class Settings(BaseSettings):
    """애플리케이션 설정
    
    .env 파일에서만 설정을 로드합니다.
    환경 변수는 무시됩니다.
    """
    
    # 애플리케이션 설정
    app_name: str = "Bank AICC Dev Server"
    debug: bool = False
    
    # 데이터베이스 설정
    database_url: str = "mysql+pymysql://root:password@localhost:3306/aicc_db?charset=utf8mb4"
    
    # OpenAI 설정
    openai_api_key: Optional[str] = None
    
    # LM Studio 설정
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "openai/gpt-oss-20b"
    use_lm_studio: bool = False  # True면 LM Studio 사용, False면 OpenAI 사용
    llm_timeout: int = 60  # LLM 호출 타임아웃 (초) - OpenAI는 빠르므로 60초로 설정
    
    # 벡터 DB 설정 (ChromaDB)
    vector_db_path: str = "./chroma_db"  # ChromaDB 저장 경로
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 한국어 지원 임베딩 모델
    collection_name: str = "financial_documents"  # ChromaDB 컬렉션 이름
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        # pydantic-settings는 자동으로 openai_api_key -> OPENAI_API_KEY로 변환합니다
        env_file_encoding = "utf-8"


# 전역 설정 인스턴스
settings = Settings()

# .env 파일에서 직접 OPENAI_API_KEY를 읽어서 강제로 설정 (환경 변수 무시)
if env_path.exists() and "OPENAI_API_KEY" in env_values and env_values["OPENAI_API_KEY"]:
    settings.openai_api_key = env_values["OPENAI_API_KEY"]
    # 환경 변수도 .env 값으로 업데이트 (다른 모듈에서 사용할 수 있도록)
    os.environ["OPENAI_API_KEY"] = env_values["OPENAI_API_KEY"]
elif original_env_key:
    # .env 파일에 없으면 원래 환경 변수 복원 (하지만 사용하지 않음)
    os.environ["OPENAI_API_KEY"] = original_env_key

