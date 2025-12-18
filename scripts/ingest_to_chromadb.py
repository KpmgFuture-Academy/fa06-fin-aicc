"""
ChromaDB에 카드 도메인 문서를 적재하는 스크립트
- kb_hana_card_38categories.json → ChromaDB 벡터 저장소
- 기존 vector_store.py의 함수 활용
"""

import json
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_engine.vector_store import (
    add_documents,
    reset_vector_store,
    get_vector_store,
    search_documents
)


# 경로 설정
DATA_FILE = BASE_DIR / "data" / "kb_hana_card_38categories.json"
FAQ_FILE = BASE_DIR / "data" / "faq_additional_coverage.json"


def load_kb_documents():
    """KB 문서 로드"""
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_faq_documents():
    """FAQ 추가 문서 로드"""
    if FAQ_FILE.exists():
        with open(FAQ_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def ingest_documents():
    """문서를 ChromaDB에 적재"""

    print("=" * 60)
    print("ChromaDB 적재 시작")
    print("=" * 60)

    # 기존 벡터 스토어 초기화
    print("\n[1/5] 기존 ChromaDB 초기화...")
    reset_vector_store()
    print("  → 초기화 완료")

    # KB 문서 로드
    print("\n[2/5] KB 문서 로드...")
    kb_docs = load_kb_documents()
    print(f"  → {len(kb_docs)}개 문서 로드 완료")

    # FAQ 추가 문서 로드
    print("\n[3/5] FAQ 추가 문서 로드...")
    faq_docs = load_faq_documents()
    print(f"  → {len(faq_docs)}개 FAQ 문서 로드 완료")

    # 모든 문서 합치기
    all_docs = kb_docs + faq_docs
    print(f"  → 총 {len(all_docs)}개 문서 준비 완료")

    # 텍스트와 메타데이터 준비
    print("\n[4/5] 문서 임베딩 및 적재...")
    texts = []
    metadatas = []

    for doc in all_docs:
        # 검색 키워드를 앞부분에 배치하여 검색 효과 향상
        content = doc['content']

        # RAG 검색 보조 키워드 섹션 추출 (있으면)
        keywords_section = ""
        faq_section = ""
        main_content = content

        # 키워드와 FAQ를 content에서 추출
        if "RAG 검색 보조 키워드" in content:
            parts = content.split("RAG 검색 보조 키워드")
            if len(parts) > 1:
                main_content = parts[0].strip()
                keyword_part = parts[1]
                # FAQ 섹션이 있으면 분리
                if "FAQ" in keyword_part:
                    kw_faq_parts = keyword_part.split("FAQ", 1)
                    keywords_section = kw_faq_parts[0].strip().lstrip('\n').strip()
                    faq_section = kw_faq_parts[1].strip() if len(kw_faq_parts) > 1 else ""
                else:
                    keywords_section = keyword_part.strip().lstrip('\n').strip()

        # 키워드를 앞에 배치: 제목 > 키워드 > FAQ > 요약 > 본문
        full_text_parts = [f"제목: {doc['title']}"]
        if keywords_section:
            full_text_parts.append(f"\n검색 키워드: {keywords_section}")
        if faq_section:
            full_text_parts.append(f"\nFAQ:\n{faq_section}")
        full_text_parts.append(f"\n요약: {doc['summary']}")
        full_text_parts.append(f"\n내용:\n{main_content}")

        full_text = "".join(full_text_parts)
        texts.append(full_text)

        # 메타데이터
        metadata = {
            "kb_id": doc['kb_id'],
            "title": doc['title'],
            "category": doc['category'],  # 도메인 코드 (PAY_BILL 등)
            "domain_name": doc['domain_name'],
            "category_code": doc['category_code'],
            "intent_code": doc['intent_code'],
            "source": f"{doc['category']}/{doc['title']}"
        }
        metadatas.append(metadata)

    # ChromaDB에 적재 (chunk_size를 2000으로 증가하여 문서 분리 방지)
    ids = add_documents(
        texts=texts,
        metadatas=metadatas,
        chunk_size=2000,
        chunk_overlap=200
    )

    print(f"  → {len(ids)}개 청크 적재 완료")

    # 적재 확인
    print("\n[5/5] 적재 결과 확인...")
    vector_store = get_vector_store()
    total_docs = vector_store._collection.count()
    print(f"  → ChromaDB 총 문서 수: {total_docs}개")

    print("\n" + "=" * 60)
    print("ChromaDB 적재 완료!")
    print("=" * 60)

    return ids


def test_search():
    """검색 테스트"""
    print("\n" + "=" * 60)
    print("검색 테스트")
    print("=" * 60)

    test_queries = [
        "카드 한도 올리고 싶어요",
        "결제일 변경하려면 어떻게 해야 하나요?",
        "포인트 조회하고 싶어요",
        "카드 분실 신고",
        "연체 대금 납부"
    ]

    for query in test_queries:
        print(f"\n[쿼리] {query}")
        results = search_documents(query, top_k=3, score_threshold=0.0)

        if results:
            for i, doc in enumerate(results[:3], 1):
                print(f"  {i}. [{doc['score']:.4f}] {doc.get('source', 'unknown')}")
                print(f"     내용: {doc['content'][:100]}...")
        else:
            print("  → 검색 결과 없음")


def main():
    """메인 실행"""
    # 적재
    ingest_documents()

    # 테스트
    test_search()


if __name__ == "__main__":
    main()
