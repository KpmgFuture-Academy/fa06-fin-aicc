"""텍스트 분할 테스트 스크립트"""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.ingestion.loader import load_kb_json
from ai_engine.ingestion.parser import extract_documents_from_payload, parse_kb_document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def test_chunking():
    """텍스트 분할 테스트"""
    print("=" * 60)
    print("텍스트 분할 테스트")
    print("=" * 60)
    
    # JSON 파일 로드
    json_path = PROJECT_ROOT / "data" / "kb_finance_insurance_kb_id_22.json"
    payload = load_kb_json(json_path)
    
    # 문서 추출
    documents = extract_documents_from_payload(payload)
    print(f"\n[INFO] 추출된 문서 수: {len(documents)}")
    
    if not documents:
        print("[ERROR] 문서를 찾을 수 없습니다.")
        return
    
    # 첫 번째 문서 파싱
    document = documents[0]
    content, metadata = parse_kb_document(document, source_path=json_path, document_index=0)
    
    print(f"\n[INFO] 원본 텍스트 길이: {len(content)} 문자")
    print(f"[INFO] 제목: {metadata.get('title', 'N/A')}")
    
    # 텍스트 분할기 생성 (기본 설정)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        length_function=len,
        separators=["\n\n", "\n", "。", ".", " ", ""]
    )
    
    # 텍스트 분할
    chunks = text_splitter.split_text(content)
    
    print(f"\n[INFO] 생성된 청크 수: {len(chunks)}")
    
    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- 청크 {i} (길이: {len(chunk)} 문자) ---")
        print(chunk[:200] + "..." if len(chunk) > 200 else chunk)


if __name__ == "__main__":
    test_chunking()

