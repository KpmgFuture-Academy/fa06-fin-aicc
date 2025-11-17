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