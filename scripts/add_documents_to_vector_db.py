"""벡터 DB에 문서를 추가하는 스크립트
사용법: python scripts/add_documents_to_vector_db.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ai_engine.vector_store import add_documents, get_vector_store


def example_add_documents():
    """예제: 금융 상품 문서를 벡터 DB에 추가"""
    
    # 예제 문서들
    documents = [
        {
            "text": """
            대출 상품 안내
            
            우리은행의 주택담보대출 상품은 다음과 같은 특징이 있습니다:
            - 대출 한도: 주택 감정가의 최대 80%
            - 금리: 연 2.5% ~ 4.5% (신용등급에 따라 변동)
            - 상환 기간: 최대 30년
            - 중도상환 수수료: 없음
            
            대출 신청 시 필요한 서류:
            1. 신분증
            2. 소득 증명서
            3. 주택 등기부등본
            4. 건강보험 자격득실 확인서
            """,
            "metadata": {
                "source": "주택담보대출_상품안내서.pdf",
                "page": 1,
                "category": "대출"
            }
        },
        {
            "text": """
            예금 상품 안내
            
            정기예금 상품:
            - 금리: 연 3.0% ~ 3.5%
            - 예치 기간: 1년, 2년, 3년
            - 최소 예치 금액: 10만원
            - 이자 지급 방식: 만기 일시 지급 또는 월 이자 지급
            
            적금 상품:
            - 금리: 연 2.0% ~ 2.5%
            - 납입 기간: 1년, 2년
            - 월 납입 한도: 10만원 ~ 100만원
            - 세금 우대 혜택: 연간 200만원까지 이자소득세 면제
            """,
            "metadata": {
                "source": "예금상품_안내서.pdf",
                "page": 1,
                "category": "예금"
            }
        },
        {
            "text": """
            대출 상환 방법 안내
            
            원리금균등분할상환:
            - 매월 동일한 금액을 상환
            - 초기에는 이자 비중이 높고, 후기에는 원금 비중이 높아짐
            - 예상 상환액 계산: 대출원금 × (월이자율 × (1+월이자율)^상환개월) / ((1+월이자율)^상환개월 - 1)
            
            원금균등분할상환:
            - 매월 동일한 원금에 이자를 더하여 상환
            - 초기 상환액이 높고, 후기로 갈수록 상환액이 감소
            - 총 이자 부담이 원리금균등분할상환보다 적음
            
            만기일시상환:
            - 만기까지 이자만 납입하고, 만기에 원금 전액 상환
            - 월 납입 부담이 적지만, 만기 상환 부담이 큼
            """,
            "metadata": {
                "source": "대출상환방법_안내서.pdf",
                "page": 1,
                "category": "대출"
            }
        }
    ]
    
    # 텍스트와 메타데이터 분리
    texts = [doc["text"] for doc in documents]
    metadatas = [doc["metadata"] for doc in documents]
    
    # 벡터 DB에 추가
    print("벡터 DB에 문서 추가 중...")
    ids = add_documents(
        texts=texts,
        metadatas=metadatas,
        chunk_size=500,  # 작은 청크로 분할 (더 정확한 검색)
        chunk_overlap=100
    )
    
    print(f"✅ {len(ids)}개의 문서 청크가 벡터 DB에 추가되었습니다.")
    print(f"문서 ID: {ids[:5]}...")  # 처음 5개만 출력
    
    # 검색 테스트
    print("\n검색 테스트:")
    from ai_engine.vector_store import search_documents
    
    test_queries = ["대출 금리", "예금 이자", "상환 방법"]
    for query in test_queries:
        results = search_documents(query, top_k=2)
        print(f"\n쿼리: '{query}'")
        for i, result in enumerate(results, 1):
            print(f"  {i}. 점수: {result['score']:.3f}, 출처: {result['source']}")
            print(f"     내용: {result['content'][:100]}...")


if __name__ == "__main__":
    try:
        example_add_documents()
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

