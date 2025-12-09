# RAG 데이터 디렉토리

## 파일 구조

```
data/
└── kb_hana_card_38categories.json   # ChromaDB 적재용 JSON (38개 카테고리)
```

## kb_hana_card_38categories.json

카드 도메인 RAG 검색을 위한 KB(Knowledge Base) 문서입니다.

### 원본 데이터
- **위치**: `ai_engine/ingestion/final_hana_card_rag_documents/`
- **형식**: 8개 docx 파일 (도메인별)
- **변환 스크립트**: `scripts/convert_docx_to_json.py`

### 데이터 스키마
```json
{
  "kb_id": 1,
  "title": "가상계좌 안내",
  "category": "PAY_BILL",
  "domain_name": "결제/청구",
  "category_code": "CAT001",
  "intent_code": "INT_PAY_VA_INFO",
  "summary": "...",
  "content": "..."
}
```

### 도메인 구성 (8개 도메인, 38개 카테고리)

| 도메인 코드 | 도메인명 | 카테고리 수 |
|-------------|----------|-------------|
| PAY_BILL | 결제/청구 | 11 |
| LIMIT_AUTH | 한도/승인 | 5 |
| DELINQ | 연체/수납 | 5 |
| LOAN | 대출 | 3 |
| BENEFIT | 포인트/혜택/바우처 | 6 |
| DOC_TAX | 증명/세금 | 3 |
| UTILITY | 공과금 | 2 |
| SEC_CARD | 인증/보안/카드관리 | 3 |

### 사용법

#### ChromaDB 적재
```bash
python scripts/ingest_to_chromadb.py
```

#### 원본 docx 수정 후 JSON 재변환
```bash
python scripts/convert_docx_to_json.py
python scripts/ingest_to_chromadb.py
```
