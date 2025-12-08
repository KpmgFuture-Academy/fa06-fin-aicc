"""WebSocket 연결 테스트 스크립트

이 스크립트는 WebSocket 엔드포인트의 연결과 메시지 송수신을 테스트합니다.

사용법:
    python test_websocket.py [session_id] [message]

예시:
    python test_websocket.py test_001 "대출 금리가 얼마인가요?"
"""

import asyncio
import json
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("❌ websockets 패키지가 설치되어 있지 않습니다.")
    print("설치 명령: pip install websockets")
    sys.exit(1)


async def test_websocket_connection(session_id: str, message: str, url: str = "ws://localhost:8000"):
    """WebSocket 연결 및 메시지 테스트"""
    
    ws_url = f"{url}/api/v1/chat/ws/{session_id}"
    
    print(f"\n{'='*60}")
    print(f"🔌 WebSocket 연결 테스트")
    print(f"{'='*60}")
    print(f"URL: {ws_url}")
    print(f"세션 ID: {session_id}")
    print(f"메시지: {message}")
    print(f"{'='*60}\n")
    
    try:
        print("⏳ WebSocket 연결 시도 중...")
        async with websockets.connect(ws_url, ping_interval=30) as websocket:
            print("✅ WebSocket 연결 성공!\n")
            
            # 연결 상태 메시지 수신 대기
            try:
                status_msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                status_data = json.loads(status_msg)
                print(f"📨 서버 상태 메시지:")
                print(f"   타입: {status_data.get('type')}")
                print(f"   메시지: {status_data.get('message')}")
                print(f"   세션: {status_data.get('session_id')}\n")
            except asyncio.TimeoutError:
                print("⚠️  상태 메시지를 받지 못했습니다 (타임아웃)\n")
            
            # 메시지 전송
            send_data = {
                "type": "message",
                "user_message": message
            }
            
            print(f"📤 메시지 전송 중... [{datetime.now().strftime('%H:%M:%S')}]")
            print(f"   {json.dumps(send_data, ensure_ascii=False, indent=2)}\n")
            
            await websocket.send(json.dumps(send_data))
            
            # 응답 수신 (처리 중 메시지 + 실제 응답)
            print("⏳ 응답 대기 중... (최대 5분)")
            
            response_count = 0
            final_response = None
            
            while True:
                try:
                    # 5분 타임아웃 (LLM 응답 대기)
                    response_msg = await asyncio.wait_for(websocket.recv(), timeout=300.0)
                    response_data = json.loads(response_msg)
                    response_count += 1
                    
                    msg_type = response_data.get("type")
                    
                    if msg_type == "processing":
                        print(f"🔄 처리 중: {response_data.get('message')}")
                    
                    elif msg_type == "response":
                        print(f"\n✅ 응답 수신! [{datetime.now().strftime('%H:%M:%S')}]")
                        final_response = response_data.get("data", {})
                        break
                    
                    elif msg_type == "error":
                        print(f"\n❌ 에러 발생: {response_data.get('message')}")
                        break
                    
                    elif msg_type == "pong":
                        print(f"🏓 Pong 수신 (연결 유지)")
                    
                    else:
                        print(f"📨 알 수 없는 메시지 타입: {msg_type}")
                
                except asyncio.TimeoutError:
                    print("\n⏱️  응답 타임아웃 (5분 경과)")
                    break
            
            # 최종 응답 출력
            if final_response:
                print(f"\n{'='*60}")
                print("📋 AI 응답 상세 정보")
                print(f"{'='*60}")
                print(f"AI 메시지: {final_response.get('ai_message')}")
                print(f"의도: {final_response.get('intent')}")
                print(f"제안 액션: {final_response.get('suggested_action')}")
                
                source_docs = final_response.get('source_documents', [])
                if source_docs:
                    print(f"\n📚 참조 문서 ({len(source_docs)}개):")
                    for i, doc in enumerate(source_docs, 1):
                        print(f"   {i}. {doc.get('source')} (페이지: {doc.get('page')}, 점수: {doc.get('score'):.4f})")
                else:
                    print("\n📚 참조 문서: 없음")
                
                print(f"{'='*60}\n")
            
            print(f"✅ 테스트 완료! (총 {response_count}개 메시지 수신)")
    
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket 오류: {e}")
        return False
    
    except ConnectionRefusedError:
        print(f"❌ 연결 거부: 서버가 실행 중인지 확인하세요.")
        print(f"   백엔드 서버: {url}")
        return False
    
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_multiple_messages(session_id: str, messages: list, url: str = "ws://localhost:8000"):
    """여러 메시지 연속 전송 테스트"""
    
    ws_url = f"{url}/api/v1/chat/ws/{session_id}"
    
    print(f"\n{'='*60}")
    print(f"🔄 연속 메시지 테스트 ({len(messages)}개 메시지)")
    print(f"{'='*60}\n")
    
    try:
        async with websockets.connect(ws_url, ping_interval=30) as websocket:
            # 연결 상태 메시지 수신
            await websocket.recv()
            
            for i, message in enumerate(messages, 1):
                print(f"\n[메시지 {i}/{len(messages)}] {message}")
                
                # 메시지 전송
                await websocket.send(json.dumps({
                    "type": "message",
                    "user_message": message
                }))
                
                # 응답 수신
                while True:
                    response_msg = await asyncio.wait_for(websocket.recv(), timeout=300.0)
                    response_data = json.loads(response_msg)
                    
                    if response_data.get("type") == "response":
                        ai_message = response_data.get("data", {}).get("ai_message", "")
                        print(f"✅ 응답: {ai_message[:100]}...")
                        break
                    
                    elif response_data.get("type") == "error":
                        print(f"❌ 에러: {response_data.get('message')}")
                        break
            
            print(f"\n✅ 모든 메시지 전송 완료!")
    
    except Exception as e:
        print(f"❌ 오류: {e}")
        return False
    
    return True


def print_usage():
    """사용법 출력"""
    print("""
WebSocket 연결 테스트 스크립트

사용법:
    python test_websocket.py [session_id] [message] [url]

인자:
    session_id  세션 ID (기본값: test_session_001)
    message     전송할 메시지 (기본값: "안녕하세요")
    url         WebSocket 서버 URL (기본값: ws://localhost:8000)

예시:
    # 기본 테스트
    python test_websocket.py
    
    # 커스텀 메시지
    python test_websocket.py test_001 "대출 금리가 얼마인가요?"
    
    # Docker 환경 (Nginx 사용)
    python test_websocket.py test_001 "안녕하세요" ws://localhost
    
    # 연속 메시지 테스트
    python test_websocket.py --multi test_001

옵션:
    --multi     여러 메시지 연속 전송 테스트
    --help      도움말 표시
""")


async def main():
    """메인 함수"""
    
    # 인자 파싱
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        return
    
    if "--multi" in sys.argv:
        # 연속 메시지 테스트
        session_id = sys.argv[2] if len(sys.argv) > 2 else "test_session_001"
        url = sys.argv[3] if len(sys.argv) > 3 else "ws://localhost:8000"
        
        messages = [
            "안녕하세요",
            "대출 금리가 얼마인가요?",
            "신용카드 발급 절차를 알려주세요",
            "상담원 연결해주세요"
        ]
        
        success = await test_multiple_messages(session_id, messages, url)
    else:
        # 단일 메시지 테스트
        session_id = sys.argv[1] if len(sys.argv) > 1 else "test_session_001"
        message = sys.argv[2] if len(sys.argv) > 2 else "안녕하세요"
        url = sys.argv[3] if len(sys.argv) > 3 else "ws://localhost:8000"
        
        success = await test_websocket_connection(session_id, message, url)
    
    if success:
        print("\n🎉 테스트 성공!")
        sys.exit(0)
    else:
        print("\n💥 테스트 실패!")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  테스트 중단됨 (Ctrl+C)")
        sys.exit(0)

