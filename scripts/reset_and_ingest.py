"""벡터 스토어 리셋 및 데이터 재인제스션 스크립트"""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.vector_store import reset_vector_store
from scripts.ingest_kb_documents import ingest_documents, find_default_data_dir
from app.core.config import settings


def main():
    """벡터 스토어를 리셋하고 데이터를 재인제스션"""
    print("=" * 60)
    print("벡터 스토어 리셋 및 데이터 재인제스션")
    print("=" * 60)
    print(f"[INFO] 사용 중인 임베딩 모델: {settings.embedding_model}")
    print()
    
    try:
        # 1. 벡터 스토어 리셋
        print("[1/2] 벡터 스토어 리셋 중...")
        reset_vector_store()
        print("[OK] 벡터 스토어 리셋 완료")
        
        # 2. 데이터 인제스션
        print("\n[2/2] 데이터 인제스션 중...")
        target_path = find_default_data_dir()
        print(f"[INFO] 데이터 경로: {target_path}")
        
        summary = ingest_documents(
            target_path=target_path,
            chunk_size=500,  # 더 큰 청크로 문맥 보존 향상
            chunk_overlap=100,  # 청크 간 연결성 강화
        )
        
        print("\n" + "=" * 60)
        print("[OK] 인제스션 완료!")
        print("=" * 60)
        print(f"   파일 수: {summary['file_count']}개")
        print(f"   문서 수: {summary['document_count']}개")
        print(f"   청크 수: {summary['chunk_count']}개")
        print(f"   임베딩 모델: {settings.embedding_model}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

