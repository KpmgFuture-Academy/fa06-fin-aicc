import { useState, useRef, useCallback, useEffect } from 'react';

interface UseRealtimeSTTReturn {
  isRecording: boolean;
  isConnected: boolean;
  transcript: string;        // 현재 인식 중인 텍스트 (부분)
  finalTranscript: string;   // 확정된 텍스트
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<string>;  // 최종 텍스트 반환
}

interface TranscriptMessage {
  type: 'connected' | 'transcript' | 'error' | 'closed';
  text?: string;
  is_final?: boolean;
  message?: string;
  seq?: number;
  confidence?: number;
}

const WS_URL = '/api/v1/realtime-stt/ws';

export const useRealtimeSTT = (): UseRealtimeSTTReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // WebSocket 연결
  const connectWebSocket = useCallback((): Promise<void> => {
    return new Promise((resolve, reject) => {
      // 현재 호스트에서 WebSocket URL 생성
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}${WS_URL}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket 연결됨');
      };

      ws.onmessage = (event) => {
        try {
          const data: TranscriptMessage = JSON.parse(event.data);

          switch (data.type) {
            case 'connected':
              console.log('실시간 STT 연결 완료');
              setIsConnected(true);
              resolve();
              break;

            case 'transcript':
              if (data.text) {
                if (data.is_final) {
                  // 확정된 텍스트
                  setFinalTranscript(prev => {
                    const newText = prev ? `${prev} ${data.text}` : data.text!;
                    return newText;
                  });
                  setTranscript('');
                } else {
                  // 부분 텍스트 (실시간 표시)
                  setTranscript(data.text);
                }
              }
              break;

            case 'error':
              console.error('STT 오류:', data.message);
              setError(data.message || '알 수 없는 오류');
              reject(new Error(data.message));
              break;

            case 'closed':
              console.log('STT 연결 종료');
              setIsConnected(false);
              break;
          }
        } catch (e) {
          console.error('메시지 파싱 오류:', e);
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket 오류:', event);
        setError('WebSocket 연결 오류');
        reject(new Error('WebSocket 연결 오류'));
      };

      ws.onclose = () => {
        console.log('WebSocket 연결 종료');
        setIsConnected(false);
        wsRef.current = null;
      };

      // 타임아웃 설정
      setTimeout(() => {
        if (!isConnected) {
          reject(new Error('연결 타임아웃'));
        }
      }, 10000);
    });
  }, [isConnected]);

  // 오디오를 16-bit PCM으로 변환하여 전송
  const startAudioCapture = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        }
      });

      streamRef.current = stream;

      // AudioContext 생성
      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      // 소스 노드 생성
      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      // ScriptProcessor를 사용하여 오디오 데이터 처리
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0);

          // Float32 -> Int16 변환 (LINEAR16)
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }

          // 바이너리로 전송
          wsRef.current.send(pcmData.buffer);
        }
      };

      // 연결
      source.connect(processor);
      processor.connect(audioContext.destination);

      console.log('오디오 캡처 시작');
    } catch (err) {
      console.error('마이크 접근 실패:', err);
      setError('마이크 접근 권한이 필요합니다.');
      throw err;
    }
  }, []);

  // 오디오 캡처 중지
  const stopAudioCapture = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    console.log('오디오 캡처 중지');
  }, []);

  // 녹음 시작
  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setTranscript('');
      setFinalTranscript('');

      // WebSocket 연결
      await connectWebSocket();

      // 오디오 캡처 시작
      await startAudioCapture();

      setIsRecording(true);
    } catch (err) {
      console.error('녹음 시작 실패:', err);
      setError('녹음 시작 실패');
      throw err;
    }
  }, [connectWebSocket, startAudioCapture]);

  // 녹음 중지
  const stopRecording = useCallback(async (): Promise<string> => {
    // 오디오 캡처 중지
    stopAudioCapture();

    // EOS 신호 전송
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('EOS');

      // 잠시 대기하여 최종 결과 수신
      await new Promise(resolve => setTimeout(resolve, 1500));
    }

    // WebSocket 종료
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsRecording(false);
    setIsConnected(false);

    // 최종 텍스트 반환
    const result = finalTranscript + (transcript ? ` ${transcript}` : '');
    return result.trim();
  }, [stopAudioCapture, finalTranscript, transcript]);

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      stopAudioCapture();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [stopAudioCapture]);

  return {
    isRecording,
    isConnected,
    transcript,
    finalTranscript,
    error,
    startRecording,
    stopRecording,
  };
};
