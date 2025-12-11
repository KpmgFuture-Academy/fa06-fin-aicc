# VAD 모듈 안내

WebRTC + Silero 하이브리드 흐름으로 동작하는 스트리밍 음성 구간 검출(VAD) 구성요소.

## 파일 설명
- `base.py`: 공통 타입(`FrameResult`)과 스트리밍 VAD 프로토콜 `VADEngine`.
- `webrtc.py`: `webrtcvad` 기반 경량 VAD. PCM16 mono를 10/20/30ms 프레임으로 잘라 구간을 집계.
- `silero.py`: Silero TorchScript VAD 래퍼. 프레임별 확률을 threshold로 판정하고 구간 집계. `SILERO_VAD_MODEL_PATH` 또는 주입된 모델 필요.
- `hybrid.py`: WebRTC 선필터 + Silero 확정 하이브리드 컨트롤러. `mode`는 `and`(둘 다) / `or`(둘 중 하나).
- `__init__.py`: 위 엔진들을 편리하게 import할 수 있도록 export.

## 전제/의존성
- 입력 오디오: PCM16 mono, 기본 16 kHz. 프레임 크기는 엔진 설정과 맞아야 함.
- Silero: `torch` 필요, Silero VAD TorchScript 모델 경로를 env `SILERO_VAD_MODEL_PATH`로 제공(또는 모델 객체 직접 주입).

## 사용 예시 (하이브리드)
```python
from app.services.vad import HybridVADStream, SileroVADStream

silero = SileroVADStream(
    sample_rate=16000,
    frame_ms=40,
    threshold=0.5,
    model_path="path/to/silero_vad.jit",
)
vad = HybridVADStream(
    silero,
    sample_rate=16000,
    frame_ms=20,
    aggressiveness=2,
    mode="and",
)

segments = []
for chunk in audio_stream:  # 작은 청크의 PCM16 바이트
    segments.extend(vad.feed(chunk))
```
