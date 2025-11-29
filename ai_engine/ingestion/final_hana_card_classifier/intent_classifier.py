"""
의도 분류기 추론 모듈
- KcELECTRA LoRA 모델 로드
- 입력 텍스트 → 카테고리 예측 + confidence 반환
- confidence_pattern (A/B/C) 판정
- meta info 생성
"""
import os
import json
import torch
from datetime import datetime
from typing import Dict, Optional, Tuple
from transformers import ElectraTokenizer, ElectraForSequenceClassification
from peft import PeftModel


class IntentClassifier:
    """의도 분류기 클래스"""

    def __init__(
        self,
        model_dir: str = './model_final',
        mapping_file: str = './category_domain_mapping.json',
        device: str = None
    ):
        """
        Args:
            model_dir: LoRA 모델 디렉토리
            mapping_file: 카테고리-도메인 매핑 JSON 파일
            device: 'cuda' 또는 'cpu' (None이면 자동 감지)
        """
        self.model_dir = model_dir
        self.mapping_file = mapping_file
        self.device = torch.device(device if device else ('cuda' if torch.cuda.is_available() else 'cpu'))

        # 매핑 데이터 로드
        self._load_mapping()

        # 모델 로드
        self._load_model()

        # 대화 카운터 (conversation_id 생성용)
        self.conversation_counter = 0

    def _load_mapping(self):
        """카테고리-도메인 매핑 로드"""
        with open(self.mapping_file, 'r', encoding='utf-8') as f:
            self.mapping_data = json.load(f)

        # confidence 임계값
        self.threshold_a = self.mapping_data['confidence_thresholds']['pattern_a']
        self.threshold_b_low = self.mapping_data['confidence_thresholds']['pattern_b_low']

        # 카테고리명 → 매핑 정보 딕셔너리 생성
        self.category_to_info = {}
        for domain in self.mapping_data['domain_mapping']:
            for cat in domain['categories']:
                self.category_to_info[cat['category_name']] = {
                    'domain_code': domain['domain_code'],
                    'domain_name': domain['domain_name'],
                    'rag_index_name': domain['rag_index_name'],
                    'category_code': cat['category_code'],
                    'category_name': cat['category_name'],
                    'intent_code': cat['intent_code']
                }

        # 카테고리 리스트 (모델 인덱스 순서대로)
        category_file = os.path.join(os.path.dirname(self.model_dir), 'preprocessed_final', 'categories.txt')
        if os.path.exists(category_file):
            with open(category_file, 'r', encoding='utf-8') as f:
                self.categories = [line.strip() for line in f if line.strip()]
        else:
            # 매핑 파일에서 카테고리 추출 (순서 보장 안됨 - 주의)
            self.categories = list(self.category_to_info.keys())

        print(f"카테고리 수: {len(self.categories)}")
        print(f"도메인 수: {len(self.mapping_data['domain_mapping'])}")

    def _load_model(self):
        """LoRA 모델 로드"""
        print(f"모델 로드 중... (device: {self.device})")

        # 토크나이저
        self.tokenizer = ElectraTokenizer.from_pretrained("beomi/KcELECTRA-base-v2022")

        # 베이스 모델
        base_model = ElectraForSequenceClassification.from_pretrained(
            "beomi/KcELECTRA-base-v2022",
            num_labels=len(self.categories)
        )

        # LoRA 어댑터 로드 및 병합
        lora_path = os.path.join(self.model_dir, 'lora_adapter')
        model = PeftModel.from_pretrained(base_model, lora_path)
        self.model = model.merge_and_unload()

        self.model.to(self.device)
        self.model.eval()

        print("모델 로드 완료!")

    def _get_confidence_pattern(self, confidence: float) -> str:
        """confidence 값에 따른 패턴 반환"""
        if confidence >= self.threshold_a:
            return "A"
        elif confidence >= self.threshold_b_low:
            return "B"
        else:
            return "C"

    def predict(
        self,
        text: str,
        max_length: int = 256,
        return_top_k: int = 3
    ) -> Dict:
        """
        텍스트 분류 예측

        Args:
            text: 입력 텍스트
            max_length: 최대 토큰 길이
            return_top_k: 상위 k개 예측 반환

        Returns:
            예측 결과 딕셔너리
        """
        # 토크나이즈
        inputs = self.tokenizer(
            text,
            max_length=max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        ).to(self.device)

        # 예측
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)

            # Top-k 결과
            top_k_probs, top_k_indices = torch.topk(probs, k=min(return_top_k, len(self.categories)), dim=-1)
            top_k_probs = top_k_probs[0].cpu().tolist()
            top_k_indices = top_k_indices[0].cpu().tolist()

        # 최고 확률 결과
        best_idx = top_k_indices[0]
        best_prob = top_k_probs[0]
        best_category = self.categories[best_idx]

        # 패턴 판정
        pattern = self._get_confidence_pattern(best_prob)

        # Top-k 카테고리 리스트
        top_k_categories = [
            {
                'category_name': self.categories[idx],
                'confidence': prob
            }
            for idx, prob in zip(top_k_indices, top_k_probs)
        ]

        return {
            'category_name': best_category,
            'confidence': best_prob,
            'confidence_pattern': pattern,
            'top_k': top_k_categories
        }

    def generate_meta_info(
        self,
        text: str,
        conversation_id: str = None,
        turn_id: int = 1
    ) -> Dict:
        """
        meta info 생성

        Args:
            text: 입력 텍스트
            conversation_id: 대화 ID (None이면 자동 생성)
            turn_id: 턴 번호

        Returns:
            meta info 딕셔너리
        """
        # 예측
        prediction = self.predict(text)

        # conversation_id 생성
        if conversation_id is None:
            self.conversation_counter += 1
            date_str = datetime.now().strftime("%Y%m%d")
            conversation_id = f"conv_{date_str}_{self.conversation_counter:04d}"

        # 카테고리 정보 조회
        category_name = prediction['category_name']
        if category_name in self.category_to_info:
            cat_info = self.category_to_info[category_name]
        else:
            # 매핑에 없는 경우 (예: 학습 데이터에는 있지만 매핑에 없는 경우)
            cat_info = {
                'domain_code': 'UNKNOWN',
                'domain_name': '알 수 없음',
                'rag_index_name': 'rag_index_unknown',
                'category_code': 'CAT000',
                'category_name': category_name,
                'intent_code': 'INT_UNKNOWN'
            }

        # meta info 구성
        meta_info = {
            "conversation_id": conversation_id,
            "turn_id": turn_id,

            "classification_result": {
                "domain_code": cat_info['domain_code'],
                "domain_name": cat_info['domain_name'],
                "category_code": cat_info['category_code'],
                "category_name": cat_info['category_name'],
                "intent_code": cat_info['intent_code'],
                "confidence": round(prediction['confidence'], 4),
                "confidence_pattern": prediction['confidence_pattern']
            },

            "rag_query": text,
            "rag_filters": {
                "rag_index_name": cat_info['rag_index_name'],
                "domain_code": cat_info['domain_code'],
                "category_code": cat_info['category_code'],
                "is_active": True
            },

            "top_k_predictions": prediction['top_k']
        }

        return meta_info


def main():
    """테스트 실행"""
    print("=" * 60)
    print("의도 분류기 테스트")
    print("=" * 60)

    # 분류기 초기화
    classifier = IntentClassifier(
        model_dir='./model_final',
        mapping_file='./category_domain_mapping.json'
    )

    # 테스트 문장
    test_sentences = [
        "이번 달 카드 결제대금이 얼마인지 알려주세요",
        "가상계좌 발급해주세요",
        "카드 분실 신고하려고요",
        "포인트 조회 부탁드려요",
        "한도 상향 신청하고 싶어요",
        "삼성페이 등록하려는데 어떻게 해요?",
        "연말정산용 소득공제 확인서 어디서 받아요?",
        "지난달 명세서 다시 받을 수 있어요?"
    ]

    print("\n테스트 결과:")
    print("-" * 60)

    for text in test_sentences:
        meta_info = classifier.generate_meta_info(text)

        print(f"\n입력: {text}")
        print(f"  → 카테고리: {meta_info['classification_result']['category_name']}")
        print(f"  → 도메인: {meta_info['classification_result']['domain_name']}")
        print(f"  → Confidence: {meta_info['classification_result']['confidence']:.4f}")
        print(f"  → Pattern: {meta_info['classification_result']['confidence_pattern']}")

    # 상세 meta info 출력 (첫 번째 예시)
    print("\n" + "=" * 60)
    print("상세 Meta Info 예시:")
    print("=" * 60)
    meta_info = classifier.generate_meta_info(test_sentences[0])
    print(json.dumps(meta_info, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
