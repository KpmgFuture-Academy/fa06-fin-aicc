/**
 * 음성 녹음 훅 (Hybrid VAD 적용 버전)
 *
 * WebSocket 스트리밍을 사용하되, 자동 전송 대신 수동 전송 방식
 * - 버튼 클릭으로 녹음 시작/중지
 * - 실시간 Hybrid VAD (WebRTC + Silero) 결과 수신
 * - 수동 중지 시 EOS 전송 → STT → AI → TTS 응답 수신
 */

import { useState, useRef, useCallback, useEffect } from 'react';

// 서버 메시지 타입
interface ServerMessage {
  type: 'connected' | 'stt_result' | 'ai_response' | 'tts_chunk' | 'completed' | 'error' | 'pong' | 'vad_result' | 'auto_send';
  data: {
    session_id?: string;
    message?: string;
    vad_config?: {
      engine: string;
      mode: string;
      threshold?: number;
      sample_rate: number;
    };
    text?: string;
    is_final?: boolean;
    intent?: string;
    suggested_action?: string;
    handover_status?: string | null;
    is_human_required_flow?: boolean;
    is_session_end?: boolean;
    audio_base64?: string;
    format?: string;
    chunk_index?: number;
    final_text?: string;
    is_speech?: boolean;
    speech_prob?: number;
    event?: 'speech_start' | 'speech_end' | 'speech_continue' | 'silence' | null;
    reason?: string;
    buffer_chunks?: number;
    duration_ms?: number;
  };
  timestamp: number;
}

// useVoiceStream과 동일한 결과 타입 사용
export interface VoiceRecordingResult {
  userText: string;
  aiResponse: {
    text: string;
    intent: string;
    suggestedAction: string;
    handoverStatus?: string | null;
    isHumanRequiredFlow?: boolean;
    isSessionEnd?: boolean;
  } | null;
  // audioBase64는 제거됨: TTS는 WebSocket을 통해 실시간으로 재생됨
}

interface UseVoiceRecordingReturn {
  isRecording: boolean;
  isProcessing: boolean;
  error: string | null;
  recordingTime: number;
  isSpeaking: boolean;        // Hybrid VAD: 현재 음성 감지 여부
  speechProb: number;         // Silero VAD: 음성 확률 (0.0 ~ 1.0)
  vadEvent: string | null;    // VAD 이벤트 (speech_start, speech_end 등)
  isPlayingTTS: boolean;      // TTS 재생 중 여부
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<VoiceRecordingResult | null>;
}

export const useVoiceRecording = (sessionId: string): UseVoiceRecordingReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechProb, setSpeechProb] = useState(0);
  const [vadEvent, setVadEvent] = useState<string | null>(null);
  const [isPlayingTTS, setIsPlayingTTS] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 응답 대기용 refs
  const responseResolverRef = useRef<((result: VoiceRecordingResult | null) => void) | null>(null);
  const latestUserTextRef = useRef<string>('');
  const latestAiResponseRef = useRef<VoiceRecordingResult['aiResponse']>(null);

  // TTS 오디오 재생용 refs
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef<boolean>(false);
  const ttsAudioContextRef = useRef<AudioContext | null>(null);

  // WebSocket URL 생성 (스트리밍 엔드포인트 사용)
  const getWsUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/api/v1/voice/streaming/${sessionId}`;
  }, [sessionId]);

  // TTS 오디오 재생 함수
  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      // 큐가 비어있고 재생 중이 아니면 TTS 완료
      if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
        setIsPlayingTTS(false);
      }
      return;
    }

    isPlayingRef.current = true;
    setIsPlayingTTS(true);
    const audioBase64 = audioQueueRef.current.shift();

    if (!audioBase64) {
      isPlayingRef.current = false;
      setIsPlayingTTS(false);
      return;
    }

    try {
      // AudioContext 초기화 (필요 시)
      if (!ttsAudioContextRef.current || ttsAudioContextRef.current.state === 'closed') {
        ttsAudioContextRef.current = new AudioContext();
      }

      // Base64 디코딩
      const binaryString = atob(audioBase64);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // MP3 디코딩 및 재생
      const audioBuffer = await ttsAudioContextRef.current.decodeAudioData(bytes.buffer);
      const source = ttsAudioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ttsAudioContextRef.current.destination);

      source.onended = () => {
        isPlayingRef.current = false;
        playNextAudio(); // 다음 청크 재생 (또는 완료 처리)
      };

      source.start(0);
      console.log('[VoiceRecording] TTS 청크 재생 중...');
    } catch (err) {
      console.error('[VoiceRecording] TTS 재생 오류:', err);
      isPlayingRef.current = false;
      playNextAudio(); // 오류 발생 시 다음 청크 시도
    }
  }, []);

  // 리샘플링 함수: 원본 샘플레이트 → 16kHz
  const resample = useCallback((inputData: Float32Array, inputSampleRate: number, outputSampleRate: number): Float32Array => {
    if (inputSampleRate === outputSampleRate) {
      return inputData;
    }

    const ratio = inputSampleRate / outputSampleRate;
    const outputLength = Math.round(inputData.length / ratio);
    const outputData = new Float32Array(outputLength);

    for (let i = 0; i < outputLength; i++) {
      const srcIndex = i * ratio;
      const srcIndexFloor = Math.floor(srcIndex);
      const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1);
      const t = srcIndex - srcIndexFloor;
      outputData[i] = inputData[srcIndexFloor] * (1 - t) + inputData[srcIndexCeil] * t;
    }

    return outputData;
  }, []);

  // WebSocket 메시지 핸들러
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: ServerMessage = JSON.parse(event.data);
      const { type, data } = message;

      console.log('[VoiceRecording] 메시지 수신:', type, data);

      switch (type) {
        case 'connected':
          console.log('[VoiceRecording] 연결 완료 - Hybrid VAD 설정:', data.vad_config);
          break;

        case 'vad_result':
          // Hybrid VAD 결과 처리
          if (data.speech_prob !== undefined) {
            setSpeechProb(data.speech_prob);
          }
          if (data.is_speech !== undefined) {
            setIsSpeaking(data.is_speech);
          }
          if (data.event) {
            setVadEvent(data.event);
          }
          break;

        case 'auto_send':
          // 녹음 모드에서는 자동 전송 무시 (수동 전송만 사용)
          console.log('[VoiceRecording] 자동 전송 트리거 무시 (수동 모드):', data.reason);
          break;

        case 'stt_result':
          if (data.text && data.is_final) {
            latestUserTextRef.current = data.text;
            console.log('[VoiceRecording] STT 결과:', data.text);
          }
          break;

        case 'ai_response':
          console.log('[VoiceRecording] AI 응답:', data.text);
          latestAiResponseRef.current = {
            text: data.text || '',
            intent: data.intent || '',
            suggestedAction: data.suggested_action || '',
            handoverStatus: data.handover_status || null,
            isHumanRequiredFlow: data.is_human_required_flow || false,
            isSessionEnd: data.is_session_end || false,
          };
          break;

        case 'tts_chunk':
          // TTS 청크 수신 시 오디오 큐에 추가하고 재생
          if (data.audio_base64) {
            console.log('[VoiceRecording] TTS 청크 수신, 재생 시작');
            audioQueueRef.current.push(data.audio_base64);
            playNextAudio();
          }
          break;

        case 'completed':
          console.log('[VoiceRecording] 처리 완료:', data.message);
          setIsProcessing(false);

          if (data.final_text) {
            latestUserTextRef.current = data.final_text;
          }

          // Promise resolver 호출
          if (responseResolverRef.current) {
            responseResolverRef.current({
              userText: latestUserTextRef.current,
              aiResponse: latestAiResponseRef.current,
            });
            responseResolverRef.current = null;
          }
          break;

        case 'error':
          const errorMsg = data.message || (data as Record<string, unknown>).error as string || '알 수 없는 오류';
          console.error('[VoiceRecording] 오류:', errorMsg);
          setError(errorMsg);
          setIsProcessing(false);

          if (responseResolverRef.current) {
            responseResolverRef.current(null);
            responseResolverRef.current = null;
          }
          break;

        case 'pong':
          break;
      }
    } catch (e) {
      console.error('[VoiceRecording] 메시지 파싱 오류:', e);
    }
  }, []);

  // WebSocket 연결
  const connectWebSocket = useCallback((): Promise<void> => {
    return new Promise((resolve, reject) => {
      const wsUrl = getWsUrl();
      console.log('[VoiceRecording] WebSocket 연결 시도:', wsUrl);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      let isResolved = false;

      const timeoutId = setTimeout(() => {
        if (!isResolved) {
          isResolved = true;
          reject(new Error('연결 타임아웃'));
        }
      }, 10000);

      ws.onopen = () => {
        console.log('[VoiceRecording] WebSocket 열림');
      };

      ws.onmessage = (event) => {
        try {
          const message: ServerMessage = JSON.parse(event.data);
          if (message.type === 'connected' && !isResolved) {
            clearTimeout(timeoutId);
            isResolved = true;
            resolve();
          }
        } catch (e) {
          // ignore
        }
        handleMessage(event);
      };

      ws.onerror = (event) => {
        console.error('[VoiceRecording] WebSocket 오류:', event);
        setError('WebSocket 연결 오류');
        clearTimeout(timeoutId);
        if (!isResolved) {
          isResolved = true;
          reject(new Error('WebSocket 연결 오류'));
        }
      };

      ws.onclose = () => {
        console.log('[VoiceRecording] WebSocket 닫힘');
        wsRef.current = null;
      };
    });
  }, [getWsUrl, handleMessage]);

  // 오디오 캡처 시작
  const startAudioCapture = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    streamRef.current = stream;

    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;

    const actualSampleRate = audioContext.sampleRate;
    console.log('[VoiceRecording] 실제 샘플레이트:', actualSampleRate);

    const source = audioContext.createMediaStreamSource(stream);
    sourceRef.current = source;

    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const inputData = e.inputBuffer.getChannelData(0);

        // 16kHz로 리샘플링
        const resampledData = resample(inputData, actualSampleRate, 16000);

        // Float32 → Int16 변환
        const pcmData = new Int16Array(resampledData.length);
        for (let i = 0; i < resampledData.length; i++) {
          const s = Math.max(-1, Math.min(1, resampledData[i]));
          pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        // 백엔드로 전송 (Hybrid VAD 처리)
        wsRef.current.send(pcmData.buffer);
      }
    };

    source.connect(processor);
    processor.connect(audioContext.destination);

    console.log('[VoiceRecording] 오디오 캡처 시작 (Hybrid VAD)');
  }, [resample]);

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
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    console.log('[VoiceRecording] 오디오 캡처 중지');
  }, []);

  // 녹음 시작
  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setRecordingTime(0);
      setIsSpeaking(false);
      setSpeechProb(0);
      setVadEvent(null);

      // 이전 결과 초기화
      latestUserTextRef.current = '';
      latestAiResponseRef.current = null;

      // WebSocket 연결
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        await connectWebSocket();
      }

      // 오디오 캡처 시작
      await startAudioCapture();

      setIsRecording(true);

      // 녹음 시간 타이머
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);

      console.log('[VoiceRecording] 녹음 시작');
    } catch (err) {
      console.error('[VoiceRecording] 녹음 시작 실패:', err);
      setError('마이크 접근 권한이 필요합니다.');
      throw err;
    }
  }, [connectWebSocket, startAudioCapture]);

  // 녹음 중지 및 전송
  const stopRecording = useCallback(async (): Promise<VoiceRecordingResult | null> => {
    return new Promise((resolve) => {
      // 타이머 중지
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      // 오디오 캡처 중지
      stopAudioCapture();

      setIsRecording(false);

      // WebSocket이 열려있으면 EOS 전송
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        setIsProcessing(true);
        responseResolverRef.current = resolve;

        console.log('[VoiceRecording] EOS 전송');
        wsRef.current.send('EOS');

        // 타임아웃 (30초)
        setTimeout(() => {
          if (responseResolverRef.current) {
            console.log('[VoiceRecording] 타임아웃');
            responseResolverRef.current({
              userText: latestUserTextRef.current,
              aiResponse: latestAiResponseRef.current,
            });
            responseResolverRef.current = null;
            setIsProcessing(false);
          }
        }, 30000);
      } else {
        console.log('[VoiceRecording] WebSocket이 열려있지 않음');
        resolve(null);
      }
    });
  }, [stopAudioCapture]);

  // WebSocket 연결 해제 (컴포넌트 언마운트 또는 세션 변경 시)
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      stopAudioCapture();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      // TTS AudioContext 정리
      if (ttsAudioContextRef.current) {
        ttsAudioContextRef.current.close();
        ttsAudioContextRef.current = null;
      }
      audioQueueRef.current = [];
    };
  }, [stopAudioCapture]);

  return {
    isRecording,
    isProcessing,
    error,
    recordingTime,
    isSpeaking,
    speechProb,
    vadEvent,
    isPlayingTTS,
    startRecording,
    stopRecording,
  };
};

export default useVoiceRecording;
