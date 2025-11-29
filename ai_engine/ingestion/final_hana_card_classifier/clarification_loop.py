"""
Clarification Loop 모듈
- Pattern B/C일 때 LLM에게 추가 질문 생성 요청
- 최대 3회 반복
- 도중에 A가 되면 즉시 종료
- 3회 후에도 A 안 나오면 LLM이 최종 카테고리 선택
"""
import os
import json
import requests
from typing import Dict, List, Optional, Tuple

from intent_classifier import IntentClassifier


class ClarificationLoop:
    """Clarification Loop 클래스"""

    def __init__(
        self,
        classifier: IntentClassifier,
        max_turns: int = 3,
        llm_model: str = "gemma3:4b",
        ollama_url: str = "http://localhost:11434"
    ):
        """
        Args:
            classifier: IntentClassifier 인스턴스
            max_turns: 최대 Clarification 횟수
            llm_model: 사용할 Ollama 모델
            ollama_url: Ollama 서버 URL
        """
        self.classifier = classifier
        self.max_turns = max_turns
        self.llm_model = llm_model
        self.ollama_url = ollama_url

        # 카테고리 리스트 (LLM에게 제공용)
        self.category_list = list(self.classifier.category_to_info.keys())

    def _call_ollama(self, prompt: str, max_tokens: int = 150) -> str:
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

    def _generate_clarification_question(
        self,
        user_query: str,
        top_k_predictions: List[Dict],
        conversation_history: List[Dict]
    ) -> str:
        """
        LLM을 사용하여 Clarification 질문 생성

        Args:
            user_query: 원본 사용자 질문
            top_k_predictions: 상위 k개 예측 결과
            conversation_history: 이전 대화 내역

        Returns:
            Clarification 질문
        """
        # 상위 예측 카테고리 정보
        top_categories = "\n".join([
            f"- {pred['category_name']} (confidence: {pred['confidence']:.2%})"
            for pred in top_k_predictions
        ])

        # 이전 대화 요약
        history_text = ""
        if conversation_history:
            history_text = "\n이전 대화:\n" + "\n".join([
                f"- 질문: {h.get('question', '')}\n  답변: {h.get('answer', '')}"
                for h in conversation_history
            ])

        prompt = f"""당신은 카드사 고객센터 상담 봇입니다.
고객의 의도를 정확히 파악하기 위해 추가 질문을 생성해야 합니다.

고객 원본 질문: "{user_query}"

현재 예측된 카테고리 후보:
{top_categories}
{history_text}

위 정보를 바탕으로, 고객의 정확한 의도를 파악하기 위한 자연스러운 추가 질문을 1개만 생성하세요.
질문은 간결하고 명확해야 하며, 위 카테고리 중 어떤 것에 해당하는지 구분할 수 있어야 합니다.

추가 질문:"""

        return self._call_ollama(prompt, max_tokens=150)

    def _llm_select_final_category(
        self,
        user_query: str,
        conversation_history: List[Dict],
        top_k_predictions: List[Dict]
    ) -> Dict:
        """
        3회 Clarification 후에도 A가 안 나온 경우 LLM이 최종 카테고리 선택

        Args:
            user_query: 원본 사용자 질문
            conversation_history: 전체 대화 내역
            top_k_predictions: 마지막 예측의 상위 k개 결과

        Returns:
            선택된 카테고리 정보
        """
        # 대화 요약
        history_text = "\n".join([
            f"- 질문: {h.get('question', '')}\n  답변: {h.get('answer', '')}"
            for h in conversation_history
        ])

        # 상위 예측 카테고리
        top_categories = "\n".join([
            f"- {pred['category_name']} (confidence: {pred['confidence']:.2%})"
            for pred in top_k_predictions
        ])

        prompt = f"""당신은 카드사 고객센터 상담 봇입니다.
고객의 의도를 최종 결정해야 합니다.

고객 원본 질문: "{user_query}"

대화 내역:
{history_text}

현재 예측된 카테고리 후보:
{top_categories}

사용 가능한 전체 카테고리:
{json.dumps(self.category_list, ensure_ascii=False)}

위 정보를 종합하여 가장 적절한 카테고리를 선택하세요.
반드시 위 "사용 가능한 전체 카테고리" 목록 중에서만 선택해야 합니다.

선택한 카테고리명만 출력하세요 (따옴표 없이):"""

        selected_category = self._call_ollama(prompt, max_tokens=50)

        # 카테고리 정보 조회
        if selected_category in self.classifier.category_to_info:
            cat_info = self.classifier.category_to_info[selected_category]
        else:
            # 가장 유사한 카테고리 찾기 (fallback)
            selected_category = top_k_predictions[0]['category_name']
            cat_info = self.classifier.category_to_info.get(selected_category, {
                'domain_code': 'UNKNOWN',
                'domain_name': '알 수 없음',
                'rag_index_name': 'rag_index_unknown',
                'category_code': 'CAT000',
                'category_name': selected_category,
                'intent_code': 'INT_UNKNOWN'
            })

        return {
            'category_name': selected_category,
            'category_info': cat_info,
            'selection_method': 'llm_final_selection'
        }

    def run(
        self,
        user_query: str,
        simulate_answers: List[str] = None,
        verbose: bool = True
    ) -> Dict:
        """
        Clarification Loop 실행

        Args:
            user_query: 사용자 질문
            simulate_answers: 시뮬레이션용 답변 리스트 (테스트용)
            verbose: 상세 출력 여부

        Returns:
            최종 분류 결과
        """
        conversation_history = []
        current_query = user_query

        if verbose:
            print(f"\n{'='*60}")
            print(f"원본 질문: {user_query}")
            print(f"{'='*60}")

        # 초기 분류
        meta_info = self.classifier.generate_meta_info(current_query)
        pattern = meta_info['classification_result']['confidence_pattern']

        if verbose:
            print(f"\n[초기 분류]")
            print(f"  카테고리: {meta_info['classification_result']['category_name']}")
            print(f"  Confidence: {meta_info['classification_result']['confidence']:.4f}")
            print(f"  Pattern: {pattern}")

        # Pattern A면 바로 반환
        if pattern == "A":
            if verbose:
                print(f"\n[OK] Pattern A - 카테고리 확정!")
            meta_info['clarification_turns'] = 0
            meta_info['final_selection_method'] = 'pattern_a_direct'
            return meta_info

        # Pattern B/C - Clarification Loop 진입
        if verbose:
            print(f"\n[!] Pattern {pattern} - Clarification Loop 진입")

        for turn in range(self.max_turns):
            if verbose:
                print(f"\n--- Clarification Turn {turn + 1}/{self.max_turns} ---")

            # 추가 질문 생성
            clarification_question = self._generate_clarification_question(
                user_query,
                meta_info['top_k_predictions'],
                conversation_history
            )

            if verbose:
                print(f"추가 질문: {clarification_question}")

            # 답변 받기 (시뮬레이션 또는 실제 입력)
            if simulate_answers and turn < len(simulate_answers):
                user_answer = simulate_answers[turn]
            else:
                user_answer = input("고객 답변: ") if simulate_answers is None else ""

            if verbose:
                print(f"고객 답변: {user_answer}")

            # 대화 기록 추가
            conversation_history.append({
                'question': clarification_question,
                'answer': user_answer
            })

            # 답변 포함하여 재분류
            combined_query = f"{user_query} {user_answer}"
            meta_info = self.classifier.generate_meta_info(combined_query)
            pattern = meta_info['classification_result']['confidence_pattern']

            if verbose:
                print(f"  → 카테고리: {meta_info['classification_result']['category_name']}")
                print(f"  → Confidence: {meta_info['classification_result']['confidence']:.4f}")
                print(f"  → Pattern: {pattern}")

            # Pattern A가 되면 즉시 종료
            if pattern == "A":
                if verbose:
                    print(f"\n[OK] Pattern A 달성 - 카테고리 확정!")
                meta_info['clarification_turns'] = turn + 1
                meta_info['conversation_history'] = conversation_history
                meta_info['final_selection_method'] = 'pattern_a_after_clarification'
                return meta_info

        # 3회 후에도 A가 안 나온 경우 - LLM 최종 선택
        if verbose:
            print(f"\n[!] {self.max_turns}회 Clarification 완료 - LLM 최종 선택")

        final_selection = self._llm_select_final_category(
            user_query,
            conversation_history,
            meta_info['top_k_predictions']
        )

        # 최종 meta_info 업데이트
        cat_info = final_selection['category_info']
        meta_info['classification_result'] = {
            'domain_code': cat_info.get('domain_code', 'UNKNOWN'),
            'domain_name': cat_info.get('domain_name', '알 수 없음'),
            'category_code': cat_info.get('category_code', 'CAT000'),
            'category_name': final_selection['category_name'],
            'intent_code': cat_info.get('intent_code', 'INT_UNKNOWN'),
            'confidence': meta_info['classification_result']['confidence'],
            'confidence_pattern': 'LLM_SELECTED'
        }
        meta_info['clarification_turns'] = self.max_turns
        meta_info['conversation_history'] = conversation_history
        meta_info['final_selection_method'] = 'llm_final_selection'

        if verbose:
            print(f"  → 최종 카테고리: {final_selection['category_name']}")

        return meta_info


def main():
    """테스트 실행"""
    print("=" * 60)
    print("Clarification Loop 테스트")
    print("=" * 60)

    # 분류기 초기화
    classifier = IntentClassifier(
        model_dir='./model_final',
        mapping_file='./category_domain_mapping.json'
    )

    # Clarification Loop 초기화 (Ollama 사용)
    clarification = ClarificationLoop(
        classifier=classifier,
        max_turns=3,
        llm_model="gemma3:4b"
    )

    # 테스트 케이스 1: Pattern B/C (Clarification 필요)
    print("\n" + "=" * 60)
    print("테스트: Pattern B/C 케이스 (시뮬레이션)")
    result = clarification.run(
        user_query="포인트 조회 부탁드려요",
        simulate_answers=[
            "네, 적립된 포인트 확인하고 싶어요",
            "마일리지로 전환하는 방법도 알고 싶어요",
            "포인트 사용 내역이요"
        ]
    )
    print(f"\n최종 결과: {result['classification_result']['category_name']}")
    print(f"선택 방법: {result['final_selection_method']}")
    print(f"Clarification 횟수: {result['clarification_turns']}")


if __name__ == '__main__':
    main()
