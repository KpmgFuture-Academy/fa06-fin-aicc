"""
docx 파일을 JSON 형식으로 변환하는 스크립트
- 8개 도메인 docx 파일 → 38개 카테고리별 JSON 문서
- 기존 RAG 파이프라인 스키마와 호환
"""

import json
import os
import re
from pathlib import Path
from docx import Document
from typing import List, Dict, Any


# 경로 설정
BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR / "ai_engine" / "ingestion" / "final_hana_card_rag_documents"
MAPPING_FILE = BASE_DIR / "ai_engine" / "ingestion" / "final_hana_card_classifier" / "category_domain_mapping.json"
OUTPUT_FILE = BASE_DIR / "data" / "kb_hana_card_38categories.json"


def load_category_mapping() -> Dict[str, Any]:
    """카테고리-도메인 매핑 로드"""
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_category_content(doc_paragraphs: List[str], category_name: str, all_categories: List[str]) -> str:
    """문서에서 특정 카테고리 섹션의 내용을 추출"""
    content_lines = []
    in_section = False

    for i, para in enumerate(doc_paragraphs):
        text = para.strip()
        if not text:
            continue

        # 카테고리 시작 감지
        if text == category_name:
            in_section = True
            continue

        if in_section:
            # 다른 카테고리 시작 감지 (종료 조건)
            if text in all_categories and text != category_name:
                break

            # 도메인 코드 라인 스킵 (BENEFIT, PAY_BILL 등)
            if re.match(r'^[A-Z_]+$', text) and len(text) < 20:
                continue

            # "이 문서는 해당 도메인의..." 스킵
            if text.startswith("이 문서는 해당 도메인의"):
                continue

            content_lines.append(text)

    return '\n'.join(content_lines)


def extract_summary(content: str, category_name: str) -> str:
    """내용에서 요약 추출 (개요 섹션 또는 첫 설명)"""
    lines = content.split('\n')

    # "은(는) 고객 카드업무 처리..." 패턴 찾기
    for line in lines:
        if '고객 카드업무 처리' in line:
            return line.strip()

    # 개요 다음 줄 찾기
    for i, line in enumerate(lines):
        if '1. 개요' in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not next_line.startswith(('•', '2.', '3.')):
                return next_line

    # 기본 요약 생성
    return f"{category_name}에 대한 안내 문서입니다."


def parse_docx_file(docx_path: Path) -> List[str]:
    """docx 파일을 파싱하여 단락 리스트 반환"""
    doc = Document(docx_path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def convert_all_documents() -> List[Dict[str, Any]]:
    """모든 docx 문서를 JSON 형식으로 변환"""

    # 매핑 로드
    mapping = load_category_mapping()

    # 전체 카테고리 목록 (종료 조건 감지용)
    all_categories = []
    for domain in mapping['domain_mapping']:
        for cat in domain['categories']:
            all_categories.append(cat['category_name'])

    # 결과 저장
    kb_documents = []
    kb_id = 1

    for domain_info in mapping['domain_mapping']:
        domain_code = domain_info['domain_code']
        domain_name = domain_info['domain_name']

        # docx 파일 경로
        docx_path = DOCS_DIR / f"{domain_code}.docx"

        if not docx_path.exists():
            print(f"[SKIP] {docx_path} 파일이 없습니다.")
            continue

        print(f"[처리중] {domain_code} ({domain_name})")

        # docx 파싱
        paragraphs = parse_docx_file(docx_path)

        # 각 카테고리별 내용 추출
        for cat_info in domain_info['categories']:
            category_name = cat_info['category_name']
            category_code = cat_info['category_code']
            intent_code = cat_info['intent_code']

            # 카테고리 내용 추출
            content = extract_category_content(paragraphs, category_name, all_categories)

            if not content:
                print(f"  [경고] {category_name} 내용을 찾을 수 없습니다.")
                # 전체 도메인 문서를 내용으로 사용
                content = '\n'.join(paragraphs)

            # 요약 추출
            summary = extract_summary(content, category_name)

            # KB 문서 생성
            kb_doc = {
                "kb_id": kb_id,
                "title": category_name,
                "category": domain_code,
                "domain_name": domain_name,
                "category_code": category_code,
                "intent_code": intent_code,
                "summary": summary,
                "content": content
            }

            kb_documents.append(kb_doc)
            print(f"  [OK] {category_name} (kb_id: {kb_id}, {len(content)}자)")
            kb_id += 1

    return kb_documents


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("docx → JSON 변환 시작")
    print("=" * 60)

    # 출력 디렉토리 생성
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 변환 실행
    kb_documents = convert_all_documents()

    # JSON 저장
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(kb_documents, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"변환 완료: {len(kb_documents)}개 문서")
    print(f"출력 파일: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
