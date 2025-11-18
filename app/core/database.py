"""데이터베이스 연결 및 세션 관리"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import settings

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # 연결 유효성 검사
    pool_recycle=3600,   # 1시간마다 연결 재사용
    echo=False  # SQL 쿼리 로깅 (개발 시 True로 설정)
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 (모델 상속용)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """데이터베이스 테이블 생성"""
    Base.metadata.create_all(bind=engine)

