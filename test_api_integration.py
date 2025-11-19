"""
프론트엔드-백엔드 통합 테스트 스크립트

사용 방법:
1. 백엔드 서버가 실행 중이어야 함 (uvicorn app.main:app --reload --port 8000)
2. 이 스크립트 실행: python test_api_integration.py
"""

import requests
import json
import time
import sys
from typing import Dict, Any, Tuple

BASE_URL = "http://localhost:8000"
TIMEOUT = 60  # 초


def print_section(title: str):
    """섹션 제목 출력"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_test(name: str):
    """테스트 시작 출력"""
    print(f"\n🧪 {name}...")


def print_success(message: str = ""):
    """성공 메시지 출력"""
    print(f"✅ 통과 {message}")


def print_error(message: str):
    """에러 메시지 출력"""
    print(f"❌ 실패: {message}")


def test_health_check() -> bool:
    """헬스체크 테스트"""
    print_test("헬스체크 테스트")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        
        if response.status_code != 200:
            print_error(f"HTTP 상태 코드: {response.status_code}")
            return False
        
        data = response.json()
        
        if data.get("status") != "healthy":
            print_error(f"상태가 'healthy'가 아님: {data.get('status')}")
            return False
        
        if data.get("database") != "connected":
            print_error(f"데이터베이스 연결 실패: {data.get('database')}")
            return False
        
        print_success(f"(상태: {data.get('status')}, DB: {data.get('database')})")
        return True
        
    except requests.exceptions.ConnectionError:
        print_error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        print(f"   예상 URL: {BASE_URL}")
        return False
    except Exception as e:
        print_error(str(e))
        return False


def test_chat_message() -> Tuple[bool, str]:
    """채팅 메시지 테스트"""
    print_test("채팅 메시지 테스트")
    
    session_id = f"test_session_{int(time.time())}"
    payload = {
        "session_id": session_id,
        "user_message": "대출 금리 얼마야?"
    }
    
    try:
        print(f"   요청: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        response = requests.post(
            f"{BASE_URL}/api/v1/chat/message",
            json=payload,
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            print_error(f"HTTP 상태 코드: {response.status_code}")
            print(f"   응답: {response.text}")
            return False, ""
        
        data = response.json()
        print(f"   응답: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        # 스키마 검증
        required_fields = ["ai_message", "intent", "suggested_action", "source_documents"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            print_error(f"필수 필드 누락: {', '.join(missing_fields)}")
            return False, ""
        
        # 타입 검증
        valid_intents = ["INFO_REQ", "COMPLAINT", "HUMAN_REQ"]
        if data["intent"] not in valid_intents:
            print_error(f"잘못된 intent 값: {data['intent']} (예상: {valid_intents})")
            return False, ""
        
        valid_actions = ["CONTINUE", "HANDOVER"]
        if data["suggested_action"] not in valid_actions:
            print_error(f"잘못된 suggested_action 값: {data['suggested_action']} (예상: {valid_actions})")
            return False, ""
        
        # source_documents 검증
        if not isinstance(data["source_documents"], list):
            print_error(f"source_documents가 리스트가 아님: {type(data['source_documents'])}")
            return False, ""
        
        print_success(f"(intent: {data['intent']}, action: {data['suggested_action']})")
        return True, session_id
        
    except requests.exceptions.Timeout:
        print_error("요청 타임아웃 (응답이 너무 오래 걸림)")
        return False, ""
    except Exception as e:
        print_error(str(e))
        import traceback
        traceback.print_exc()
        return False, ""


def test_handover(session_id: str) -> bool:
    """상담원 이관 테스트"""
    print_test("상담원 이관 테스트")
    
    payload = {
        "session_id": session_id,
        "trigger_reason": "USER_REQUEST"
    }
    
    try:
        print(f"   요청: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        response = requests.post(
            f"{BASE_URL}/api/v1/handover/analyze",
            json=payload,
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            print_error(f"HTTP 상태 코드: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
        
        data = response.json()
        print(f"   응답: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        # 스키마 검증
        if "status" not in data:
            print_error("'status' 필드가 없음")
            return False
        
        if "analysis_result" not in data:
            print_error("'analysis_result' 필드가 없음")
            return False
        
        analysis = data["analysis_result"]
        
        # analysis_result 필드 검증
        required_fields = ["customer_sentiment", "summary", "extracted_keywords", "kms_recommendations"]
        missing_fields = [field for field in required_fields if field not in analysis]
        
        if missing_fields:
            print_error(f"analysis_result에 필수 필드 누락: {', '.join(missing_fields)}")
            return False
        
        # 타입 검증
        valid_sentiments = ["POSITIVE", "NEGATIVE", "NEUTRAL"]
        if analysis["customer_sentiment"] not in valid_sentiments:
            print_error(f"잘못된 customer_sentiment 값: {analysis['customer_sentiment']} (예상: {valid_sentiments})")
            return False
        
        if not isinstance(analysis["extracted_keywords"], list):
            print_error(f"extracted_keywords가 리스트가 아님: {type(analysis['extracted_keywords'])}")
            return False
        
        if not isinstance(analysis["kms_recommendations"], list):
            print_error(f"kms_recommendations가 리스트가 아님: {type(analysis['kms_recommendations'])}")
            return False
        
        print_success(f"(sentiment: {analysis['customer_sentiment']}, 키워드 수: {len(analysis['extracted_keywords'])})")
        return True
        
    except requests.exceptions.Timeout:
        print_error("요청 타임아웃 (응답이 너무 오래 걸림)")
        return False
    except Exception as e:
        print_error(str(e))
        import traceback
        traceback.print_exc()
        return False


def test_error_handling() -> bool:
    """에러 처리 테스트"""
    print_test("에러 처리 테스트")
    
    # 빈 session_id 테스트
    try:
        payload = {
            "session_id": "",
            "user_message": "테스트"
        }
        response = requests.post(
            f"{BASE_URL}/api/v1/chat/message",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 400:
            print_success("빈 session_id에 대한 적절한 에러 응답")
        else:
            print_error(f"예상: 400, 실제: {response.status_code}")
            return False
        
        # 빈 user_message 테스트
        payload = {
            "session_id": "test",
            "user_message": ""
        }
        response = requests.post(
            f"{BASE_URL}/api/v1/chat/message",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 400:
            print_success("빈 user_message에 대한 적절한 에러 응답")
            return True
        else:
            print_error(f"예상: 400, 실제: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(str(e))
        return False


def test_api_schema_consistency() -> bool:
    """API 스키마 일관성 테스트"""
    print_test("API 스키마 일관성 테스트")
    
    try:
        # Swagger/OpenAPI 스키마 확인
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        
        if response.status_code != 200:
            print_error(f"OpenAPI 스키마를 가져올 수 없음: {response.status_code}")
            return False
        
        openapi_schema = response.json()
        
        # 채팅 메시지 엔드포인트 확인
        chat_path = "/api/v1/chat/message"
        if chat_path not in openapi_schema.get("paths", {}):
            print_error(f"채팅 메시지 엔드포인트를 찾을 수 없음: {chat_path}")
            return False
        
        # 상담원 이관 엔드포인트 확인
        handover_path = "/api/v1/handover/analyze"
        if handover_path not in openapi_schema.get("paths", {}):
            print_error(f"상담원 이관 엔드포인트를 찾을 수 없음: {handover_path}")
            return False
        
        print_success("OpenAPI 스키마 확인 완료")
        return True
        
    except Exception as e:
        print_error(str(e))
        return False


def main():
    """메인 테스트 실행"""
    print_section("프론트엔드-백엔드 통합 테스트")
    print(f"테스트 대상 서버: {BASE_URL}")
    print(f"타임아웃: {TIMEOUT}초")
    
    results = []
    
    # 1. 헬스체크
    results.append(("헬스체크", test_health_check()))
    
    if not results[0][1]:
        print("\n⚠️  백엔드 서버가 실행 중이지 않습니다. 테스트를 중단합니다.")
        print("   백엔드 서버를 시작하려면:")
        print("   cd fa06-fin-aicc")
        print("   uvicorn app.main:app --reload --port 8000")
        sys.exit(1)
    
    # 2. API 스키마 일관성 확인
    results.append(("API 스키마 일관성", test_api_schema_consistency()))
    
    # 3. 채팅 메시지 테스트
    chat_success, session_id = test_chat_message()
    results.append(("채팅 메시지", chat_success))
    
    # 4. 상담원 이관 테스트 (채팅이 성공한 경우에만)
    if chat_success and session_id:
        # 여러 메시지를 보내서 대화 이력을 만듦
        print("\n   대화 이력 생성 중...")
        for i in range(2):
            test_payload = {
                "session_id": session_id,
                "user_message": f"추가 질문 {i+1}"
            }
            try:
                requests.post(
                    f"{BASE_URL}/api/v1/chat/message",
                    json=test_payload,
                    timeout=TIMEOUT
                )
            except:
                pass
        
        time.sleep(1)  # DB 저장 대기
        results.append(("상담원 이관", test_handover(session_id)))
    else:
        results.append(("상담원 이관", False))
        print("\n⚠️  채팅 메시지 테스트 실패로 인해 상담원 이관 테스트를 건너뜁니다.")
    
    # 5. 에러 처리 테스트
    results.append(("에러 처리", test_error_handling()))
    
    # 결과 요약
    print_section("테스트 결과 요약")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ 통과" if success else "❌ 실패"
        print(f"  {status} - {name}")
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed*100//total if total > 0 else 0}%)")
    
    if passed == total:
        print("\n🎉 모든 테스트 통과!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed}개 테스트 실패")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  테스트가 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



