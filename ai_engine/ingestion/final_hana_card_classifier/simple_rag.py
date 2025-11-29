"""
간단한 RAG 테스트 모듈
- Ollama + 도메인별 문서 기반
- 벡터 검색 없이 도메인 매칭으로 문서 선택
"""
import os
import json
import requests
from docx import Document
from typing import Dict, List, Optional


class SimpleRAG:
    """간단한 RAG 클래스 (도메인 기반 문서 검색)"""

    def __init__(
        self,
        docs_dir: str = './Domain_Full_Templates/Domain_Full_Templates_NEW',
        mapping_file: str = './category_domain_mapping.json',
        ollama_url: str = "http://localhost:11434",
        llm_model: str = "gemma3:4b"
    ):
        self.docs_dir = docs_dir
        self.ollama_url = ollama_url
        self.llm_model = llm_model

        # 매핑 로드
        with open(mapping_file, 'r', encoding='utf-8') as f:
            self.mapping = json.load(f)

        # 도메인별 문서 로드
        self.domain_docs = {}
        self._load_documents()

    def _load_documents(self):
        """도메인별 문서 로드"""
        domain_files = {
            'PAY_BILL': 'PAY_BILL.docx',
            'LIMIT_AUTH': 'LIMIT_AUTH.docx',
            'DELINQ': 'DELINQ.docx',
            'LOAN': 'LOAN.docx',
            'BENEFIT': 'BENEFIT.docx',
            'DOC_TAX': 'DOC_TAX.docx',
            'UTILITY': 'UTILITY.docx',
            'SEC_CARD': 'SEC_CARD.docx'
        }

        for domain_code, filename in domain_files.items():
            filepath = os.path.join(self.docs_dir, filename)
            if os.path.exists(filepath):
                try:
                    doc = Document(filepath)
                    text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
                    self.domain_docs[domain_code] = text
                    print(f"[OK] {domain_code}: {len(text)} chars loaded")
                except Exception as e:
                    print(f"[ERROR] {domain_code}: {e}")
            else:
                print(f"[SKIP] {domain_code}: file not found")

    def _extract_category_section(self, domain_code: str, category_name: str) -> str:
        """도메인 문서에서 특정 카테고리 섹션 추출"""
        if domain_code not in self.domain_docs:
            return ""

        full_doc = self.domain_docs[domain_code]

        # 카테고리명으로 섹션 찾기
        lines = full_doc.split('\n')
        section_lines = []
        in_section = False
        section_depth = 0

        for line in lines:
            # 카테고리 시작 감지
            if category_name in line and not in_section:
                in_section = True
                section_lines.append(line)
                continue

            if in_section:
                # 다른 주요 섹션 시작 감지 (종료 조건)
                if line.strip() and (
                    line.startswith('CAT') or
                    (line[0].isdigit() and '.' in line[:5] and '개요' in line) or
                    any(cat in line for cat in self._get_other_categories(domain_code, category_name))
                ):
                    # 다른 카테고리 섹션 시작이면 종료
                    if any(cat in line for cat in self._get_other_categories(domain_code, category_name)):
                        break

                section_lines.append(line)

                # 최대 길이 제한
                if len('\n'.join(section_lines)) > 3000:
                    break

        result = '\n'.join(section_lines)

        # 섹션을 못 찾으면 전체 문서의 앞부분 반환
        if len(result) < 100:
            return full_doc[:3000]

        return result

    def _get_other_categories(self, domain_code: str, current_category: str) -> List[str]:
        """해당 도메인의 다른 카테고리 목록"""
        for domain in self.mapping['domain_mapping']:
            if domain['domain_code'] == domain_code:
                return [cat['category_name'] for cat in domain['categories'] if cat['category_name'] != current_category]
        return []

    def _call_ollama(self, prompt: str, max_tokens: int = 500) -> str:
        """Ollama API 호출"""
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.7
                }
            }
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def generate_response(
        self,
        user_query: str,
        meta_info: Dict,
        max_context_length: int = 2000
    ) -> Dict:
        """
        RAG 기반 응답 생성

        Args:
            user_query: 사용자 질문
            meta_info: 분류기에서 생성한 메타 정보
            max_context_length: 컨텍스트 최대 길이

        Returns:
            응답 결과
        """
        domain_code = meta_info['classification_result']['domain_code']
        category_name = meta_info['classification_result']['category_name']

        # 관련 문서 섹션 추출
        context = self._extract_category_section(domain_code, category_name)
        if len(context) > max_context_length:
            context = context[:max_context_length]

        # 프롬프트 구성
        prompt = f"""당신은 카드사 고객센터 상담 봇입니다.
아래 참고 문서를 바탕으로 고객의 질문에 친절하고 정확하게 답변하세요.

[참고 문서]
{context}

[고객 질문]
{user_query}

[답변 지침]
- 참고 문서의 내용을 기반으로 답변하세요
- 문서에 없는 내용은 추측하지 마세요
- 친절하고 명확하게 답변하세요
- 필요시 추가 확인이 필요한 사항을 안내하세요

답변:"""

        # LLM 호출
        response = self._call_ollama(prompt, max_tokens=500)

        return {
            'user_query': user_query,
            'domain_code': domain_code,
            'category_name': category_name,
            'context_used': context[:500] + '...' if len(context) > 500 else context,
            'response': response
        }


def main():
    """테스트 실행"""
    from intent_classifier import IntentClassifier

    print("=" * 60)
    print("Simple RAG 테스트")
    print("=" * 60)

    # 분류기 초기화
    print("\n[1] 분류기 로드...")
    classifier = IntentClassifier(
        model_dir='./model_final',
        mapping_file='./category_domain_mapping.json'
    )

    # RAG 초기화
    print("\n[2] RAG 문서 로드...")
    rag = SimpleRAG(
        docs_dir='./Domain_Full_Templates/Domain_Full_Templates_NEW',
        mapping_file='./category_domain_mapping.json'
    )

    # 테스트 질문
    test_queries = [
        "가상계좌 발급 방법 알려주세요",
        "카드 분실 신고하려고요",
        "포인트 조회하고 싶어요"
    ]

    print("\n[3] 테스트 실행...")
    for query in test_queries:
        print("\n" + "=" * 60)
        print(f"질문: {query}")
        print("-" * 60)

        # 분류
        meta_info = classifier.generate_meta_info(query)
        print(f"분류: {meta_info['classification_result']['category_name']}")
        print(f"도메인: {meta_info['classification_result']['domain_name']}")
        print(f"Confidence: {meta_info['classification_result']['confidence']:.4f}")
        print(f"Pattern: {meta_info['classification_result']['confidence_pattern']}")

        # RAG 응답 생성
        print("-" * 60)
        result = rag.generate_response(query, meta_info)
        print(f"응답:\n{result['response']}")


if __name__ == '__main__':
    main()
