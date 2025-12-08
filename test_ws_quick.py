#!/usr/bin/env python3
"""빠른 WebSocket 연결 테스트"""

import asyncio
import sys

async def test_ws():
    try:
        import websockets
    except ImportError:
        print("❌ websockets 패키지가 설치되어 있지 않습니다.")
        print("설치: pip install websockets")
        return False
    
    url = "ws://localhost:8000/api/v1/chat/ws/test_quick_001"
    print(f"🔌 WebSocket 연결 시도: {url}")
    
    try:
        async with websockets.connect(url, open_timeout=5) as ws:
            print("✅ WebSocket 연결 성공!")
            
            # 상태 메시지 수신
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"📨 서버 응답: {msg}")
            
            return True
    except asyncio.TimeoutError:
        print("⏱️  타임아웃: 서버 응답 없음")
        return False
    except ConnectionRefusedError:
        print("❌ 연결 거부: 백엔드 서버가 실행 중인지 확인하세요")
        return False
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_ws())
    sys.exit(0 if result else 1)

