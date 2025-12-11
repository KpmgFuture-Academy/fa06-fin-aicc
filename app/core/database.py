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
    echo=False,  # SQL 쿼리 로깅 (개발 시 True로 설정)
    connect_args={
        "connect_timeout": 5,  # 연결 타임아웃 5초 (MySQL)
    } if "mysql" in settings.database_url.lower() else {}
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
    """데이터베이스 테이블 생성 및 마이그레이션"""
    Base.metadata.create_all(bind=engine)

    # 마이그레이션: 기존 테이블에 새 컬럼 추가
    _migrate_add_column_if_not_exists(
        "chat_sessions",
        "context_intent",
        "VARCHAR(100)"
    )


def _migrate_add_column_if_not_exists(table_name: str, column_name: str, column_type: str):
    """기존 테이블에 컬럼이 없으면 추가하는 마이그레이션 헬퍼"""
    from sqlalchemy import text

    with engine.connect() as conn:
        # SQLite: PRAGMA table_info로 컬럼 존재 여부 확인
        if "sqlite" in settings.database_url.lower():
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result.fetchall()]

            if column_name not in columns:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                conn.commit()
                print(f"[DB Migration] Added column '{column_name}' to table '{table_name}'")
        else:
            # MySQL/PostgreSQL: information_schema로 확인
            try:
                result = conn.execute(text(f"""
                    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = '{table_name}' AND COLUMN_NAME = '{column_name}'
                """))
                if not result.fetchone():
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                    conn.commit()
                    print(f"[DB Migration] Added column '{column_name}' to table '{table_name}'")
            except Exception as e:
                print(f"[DB Migration] Warning: Could not check/add column: {e}")

