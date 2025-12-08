# 공통 용어 사전
# 고객 의도가 '단순 질문'인지 '화난 민원'인지 '상담원 연결'인지 정해둔 단어장
# 오타 방지용

from enum import Enum

class IntentType(str, Enum):   # 챗봇 의도 타입
    INFO_REQ = "INFO_REQ"
    COMPLAINT = "COMPLAINT"
    HUMAN_REQ = "HUMAN_REQ"

class ActionType(str, Enum):   # 챗봇 행동 타입
    CONTINUE = "CONTINUE"
    HANDOVER = "HANDOVER"

class SentimentType(str, Enum): # 고객 감정 상태
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"

class TriageDecisionType(str, Enum):  # Triage 에이전트 의사결정 타입
    AUTO_HANDLE_OK = "AUTO_HANDLE_OK"      # 자동 처리 가능 (답변 생성)
    NEED_MORE_INFO = "NEED_MORE_INFO"     # 추가 정보 필요 (질문 생성)
    HUMAN_REQUIRED = "HUMAN_REQUIRED"      # 상담사 연결 필요