"""
BERT 의도 분류 추론
학습된 모델로 실시간 예측

사용법:
    # 기본 사용 (자동 경로 탐색)
    from scripts.inference import IntentClassifier
    classifier = IntentClassifier()
    intent, confidence = classifier.predict_single("신용카드 발급하고 싶어요")

    # 커스텀 경로 지정
    classifier = IntentClassifier(model_path='/path/to/model')
"""

import json
import os
import sys
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


class IntentClassifier:
    """BERT 기반 의도 분류기"""

    def __init__(self, model_path=None):
        """모델 초기화

        Args:
            model_path (str, optional): 모델 경로. None일 경우 자동 탐색.
        """
        # 모델 경로 자동 탐색
        if model_path is None:
            model_path = self._find_model_path()

        # 경로 정규화
        model_path = os.path.abspath(model_path)

        # 모델 경로 검증
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"\n{'='*80}\n"
                f"[ERROR] 모델을 찾을 수 없습니다: {model_path}\n\n"
                f"다음을 확인하세요:\n"
                f"  1. 모델 다운로드: MODEL_DOWNLOAD.md 참조\n"
                f"  2. 모델 위치: models/bert_intent_classifier/ 폴더에 배치\n"
                f"  3. 현재 작업 디렉토리: {os.getcwd()}\n"
                f"  4. 또는 IntentClassifier(model_path='경로')로 직접 지정\n"
                f"{'='*80}\n"
            )

        print(f"\n[INFO] 모델 경로: {model_path}")

        # GPU/CPU 설정
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # 모델 및 토크나이저 로드
        print(f"[INFO] 모델 로드 중...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.to(self.device)
        self.model.eval()

        # 라벨 매핑 로드
        id2intent_path = os.path.join(model_path, 'id2intent.json')
        with open(id2intent_path, 'r', encoding='utf-8') as f:
            id2intent = json.load(f)
            self.id2intent = {int(k): v for k, v in id2intent.items()}

        print(f"[OK] 모델 로드 완료 ({self.device})")
        print(f"[OK] 의도 종류: {len(self.id2intent):,}개\n")

    def _find_model_path(self):
        """모델 경로 자동 탐색"""
        # 탐색할 경로 후보들
        candidates = [
            # 1. 현재 스크립트 위치 기준 (scripts/에서 실행)
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '../models/bert_intent_classifier'),

            # 2. 현재 작업 디렉토리 기준
            os.path.join(os.getcwd(), 'models/bert_intent_classifier'),

            # 3. 상위 디렉토리 기준
            os.path.join(os.getcwd(), '../models/bert_intent_classifier'),

            # 4. 프로젝트 루트로 추정되는 위치
            os.path.join(os.path.dirname(os.getcwd()), 'models/bert_intent_classifier'),
        ]

        # 첫 번째로 존재하는 경로 반환
        for path in candidates:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return abs_path

        # 못 찾으면 기본 경로 반환 (에러 메시지용)
        return os.path.abspath('models/bert_intent_classifier')

    def predict(self, text, top_k=1):
        """텍스트의 의도 예측 (Top-K)

        Args:
            text (str): 입력 텍스트
            top_k (int): 상위 K개 결과 반환

        Returns:
            list: [{'intent': str, 'confidence': float}, ...]
        """
        # 토크나이징
        inputs = self.tokenizer(
            text,
            return_tensors='pt',
            max_length=128,
            padding='max_length',
            truncation=True
        ).to(self.device)

        # 예측
        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)

        # Top-k 결과
        top_probs, top_indices = torch.topk(probabilities[0], k=min(top_k, len(self.id2intent)))

        results = []
        for prob, idx in zip(top_probs, top_indices):
            results.append({
                'intent': self.id2intent[idx.item()],
                'confidence': prob.item()
            })

        return results

    def predict_single(self, text):
        """단일 의도 예측 (가장 높은 확률)

        Args:
            text (str): 입력 텍스트

        Returns:
            tuple: (intent, confidence)
        """
        result = self.predict(text, top_k=1)[0]
        return result['intent'], result['confidence']


# ============================================================================
# 커맨드 라인 실행
# ============================================================================

if __name__ == "__main__":
    import argparse

    # 인자 파싱
    parser = argparse.ArgumentParser(description='BERT 의도 분류 추론')
    parser.add_argument('--model', type=str, default=None, help='모델 경로 (기본: 자동 탐색)')
    parser.add_argument('--text', type=str, default=None, help='분류할 텍스트 (기본: 대화형 모드)')
    parser.add_argument('--top-k', type=int, default=3, help='Top-K 결과 개수 (기본: 3)')
    args = parser.parse_args()

    # 분류기 초기화
    try:
        classifier = IntentClassifier(model_path=args.model)
    except FileNotFoundError as e:
        print(e)
        print("\n[도움말] 모델 다운로드 방법은 MODEL_DOWNLOAD.md를 참조하세요.")
        sys.exit(1)

    # 단일 텍스트 모드
    if args.text:
        results = classifier.predict(args.text, top_k=args.top_k)

        print("=" * 80)
        print(f"질문: {args.text}")
        print("=" * 80)
        print("예측 결과:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result['intent']:30s} ({result['confidence']:.2%})")
        print("=" * 80)
        sys.exit(0)

    # 대화형 모드
    print("=" * 80)
    print("BERT 의도 분류 - 대화형 모드")
    print("=" * 80)
    print("종료: 'quit', 'exit', '종료' 입력")
    print("=" * 80)

    # 테스트 샘플
    test_texts = [
        "신용카드를 만들고 싶어요",
        "보험 청구는 어떻게 하나요?",
        "계좌 잔고를 확인하고 싶습니다",
        "대출 금리가 궁금합니다",
        "비밀번호를 변경하고 싶어요",
    ]

    print("\n[테스트 샘플]")
    for i, text in enumerate(test_texts, 1):
        results = classifier.predict(text, top_k=3)

        print(f"\n{i}. 질문: {text}")
        print("   예측 결과:")
        for j, result in enumerate(results, 1):
            print(f"     {j}. {result['intent']:30s} ({result['confidence']:.2%})")

    # 대화형 루프
    print("\n" + "=" * 80)
    print("대화형 모드 시작")
    print("=" * 80)

    while True:
        try:
            user_input = input("\n질문을 입력하세요: ").strip()

            if user_input.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n종료합니다.")
                break

            if not user_input:
                continue

            # 예측
            intent, confidence = classifier.predict_single(user_input)
            print(f"→ 예측 의도: {intent} (신뢰도: {confidence:.2%})")

            # 낮은 신뢰도 경고
            if confidence < 0.6:
                print("[WARNING] 낮은 신뢰도: 인간 상담사 연결 권장")

        except KeyboardInterrupt:
            print("\n\n종료합니다.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
