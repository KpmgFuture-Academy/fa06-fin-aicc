/**
 * 양방향 실시간 음성 스트리밍 훅 (Silero VAD 버전)
 *
 * 기능:
 * - 백엔드 Silero VAD를 사용한 정확한 음성 활동 감지
 * - 실시간 STT (VITO WebSocket)
 * - AI 워크플로우 응답
 * - TTS 오디오 스트리밍 재생
 * - Barge-in 지원 (Silero VAD 기반)
 *
 * 변경점 (RMS → Silero VAD):
 * - 프론트엔드 RMS 기반 VAD 제거
 * - 백엔드에서 Silero VAD 결과 수신
 * - 더 정확한 음성/비음성 구분
 */

import { useState, useRef, useCallback, useEffect } from 'react';

// 서버 메시지 타입
interface ServerMessage {
  type: 'connected' | 'stt_result' | 'ai_response' | 'tts_chunk' | 'completed' | 'error' | 'pong' | 'vad_result' | 'auto_send';
  data: {
    // connected
    session_id?: string;
    message?: string;
    vad_config?: {
      threshold: number;
      sample_rate: number;
      min_silence_duration_ms: number;
    };
    // stt_result
    text?: string;
    is_final?: boolean;
    seq?: number;
    confidence?: number;
    // ai_response
    intent?: string;
    suggested_action?: string;
    // tts_chunk
    audio_base64?: string;
    format?: string;
    chunk_index?: number;
    // completed
    final_text?: string;
    // vad_result (Silero VAD)
    is_speech?: boolean;
    speech_prob?: number;
    event?: 'speech_start' | 'speech_end' | null;
    // auto_send
    reason?: string;
    buffer_chunks?: number;
  };
  timestamp: number;
}

interface AIResponse {
  text: string;
  intent: string;
  suggestedAction: string;
}

// stopRecording 반환 타입
export interface StopRecordingResult {
  userText: string;        // 사용자가 말한 텍스트
  aiResponse: AIResponse | null;  // AI 응답
}

interface UseVoiceStreamReturn {
  isRecording: boolean;
  isConnected: boolean;
  isProcessing: boolean;
  isPlayingTTS: boolean;       // TTS 재생 중인지
  isSpeaking: boolean;         // Silero VAD: 사용자가 말하는 중인지
  speechProb: number;          // Silero VAD: 음성 확률 (0.0 ~ 1.0)
  transcript: string;          // 현재 인식 중인 텍스트 (부분)
  finalTranscript: string;     // 확정된 텍스트
  aiResponse: AIResponse | null;
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<StopRecordingResult | null>;
  disconnect: () => void;
  setOnAutoStop: (callback: (result: StopRecordingResult | null) => void) => void;  // VAD 자동 중지 콜백 (결과 포함)
  setOnTTSComplete: (callback: () => void) => void;  // TTS 재생 완료 콜백
  setOnBargeIn: (callback: () => void) => void;  // Barge-in 콜백 (TTS 중 사용자 말하기)
}

export const useVoiceStream = (sessionId: string): UseVoiceStreamReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPlayingTTS, setIsPlayingTTS] = useState(false);  // TTS 재생 상태
  const [isSpeaking, setIsSpeaking] = useState(false);      // Silero VAD: 말하는 중
  const [speechProb, setSpeechProb] = useState(0);          // Silero VAD: 음성 확률
  const [transcript, setTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [aiResponse, setAiResponse] = useState<AIResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // 자동 중지 관련 ref
  const isAutoStoppingRef = useRef<boolean>(false);

  // TTS 재생용
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const ttsCompleteCallbackRef = useRef<(() => void) | null>(null);  // TTS 완료 콜백
  const bargeInCallbackRef = useRef<(() => void) | null>(null);  // Barge-in 콜백
  const hasTTSStartedRef = useRef<boolean>(false);  // TTS가 시작되었는지 (완료 감지용)

  // Promise resolver (stopRecording에서 결과 대기용)
  const responseResolverRef = useRef<((result: StopRecordingResult | null) => void) | null>(null);

  // AI 응답 저장용 ref (클로저 문제 해결)
  const latestAiResponseRef = useRef<AIResponse | null>(null);

  // 사용자 텍스트 저장용 ref (서버에서 받은 final_text)
  const latestUserTextRef = useRef<string>('');

  // handleMessage ref (클로저 문제 해결)
  const handleMessageRef = useRef<((event: MessageEvent) => void) | null>(null);

  // 자동 중지 콜백 ref (결과 포함)
  const autoStopCallbackRef = useRef<((result: StopRecordingResult | null) => void) | null>(null);

  // triggerAutoStop ref (클로저 문제 해결)
  const triggerAutoStopRef = useRef<(() => void) | null>(null);

  // WebSocket URL 생성
  const getWsUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/api/v1/voice/streaming/${sessionId}`;
  }, [sessionId]);

  // base64 → Blob 변환
  const base64ToBlob = useCallback((base64: string, mimeType: string): Blob => {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
  }, []);

  // TTS 재생 중지
  const stopTTS = useCallback(() => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.currentTime = 0;
    }
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    hasTTSStartedRef.current = false;
    setIsPlayingTTS(false);
  }, []);

  // TTS 오디오 재생 (큐 기반)
  const playNextAudio = useCallback(() => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      // 큐가 비어있고 재생 중이 아니면 TTS 완료
      if (!isPlayingRef.current && audioQueueRef.current.length === 0 && hasTTSStartedRef.current) {
        console.log('[VoiceStream] TTS 재생 완료');
        setIsPlayingTTS(false);
        hasTTSStartedRef.current = false;

        // TTS 완료 콜백 호출
        if (ttsCompleteCallbackRef.current) {
          console.log('[VoiceStream] TTS 완료 콜백 호출');
          ttsCompleteCallbackRef.current();
        }
      }
      return;
    }

    const base64Audio = audioQueueRef.current.shift();
    if (!base64Audio) return;

    isPlayingRef.current = true;
    setIsPlayingTTS(true);
    hasTTSStartedRef.current = true;  // TTS 시작됨 표시

    try {
      const audioBlob = base64ToBlob(base64Audio, 'audio/mp3');
      const audioUrl = URL.createObjectURL(audioBlob);

      if (!audioElementRef.current) {
        audioElementRef.current = new Audio();
      }

      const audio = audioElementRef.current;
      audio.src = audioUrl;

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        isPlayingRef.current = false;
        playNextAudio(); // 다음 청크 재생 (또는 완료 처리)
      };

      audio.onerror = () => {
        URL.revokeObjectURL(audioUrl);
        isPlayingRef.current = false;
        playNextAudio();
      };

      audio.play().catch((err) => {
        console.warn('오디오 재생 실패:', err);
        isPlayingRef.current = false;
        playNextAudio();
      });
    } catch (err) {
      console.error('오디오 처리 오류:', err);
      isPlayingRef.current = false;
      playNextAudio();
    }
  }, [base64ToBlob]);

  // WebSocket 메시지 핸들러
  const handleMessage = (event: MessageEvent) => {
    try {
      const message: ServerMessage = JSON.parse(event.data);
      const { type, data } = message;

      console.log('[VoiceStream] 메시지 수신:', type, data);

      switch (type) {
        case 'connected':
          console.log('[VoiceStream] 연결 완료:', data.message);
          if (data.vad_config) {
            console.log('[VoiceStream] Silero VAD 설정:', data.vad_config);
          }
          setIsConnected(true);
          break;

        case 'vad_result':
          // Silero VAD 결과 처리
          if (data.speech_prob !== undefined) {
            setSpeechProb(data.speech_prob);
          }
          if (data.is_speech !== undefined) {
            setIsSpeaking(data.is_speech);
          }

          // Barge-in 감지 (TTS 재생 중 음성 시작)
          if (data.event === 'speech_start' && (isPlayingRef.current || hasTTSStartedRef.current)) {
            console.log('[VoiceStream] Barge-in 감지 (Silero VAD)! prob:', data.speech_prob);
            stopTTS();

            // 현재 처리 상태 리셋 (새 발화 준비)
            isAutoStoppingRef.current = false;
            setIsProcessing(false);
            setIsRecording(true);  // 녹음 상태로 전환

            // 이전 텍스트 초기화
            setTranscript('');
            setFinalTranscript('');

            if (bargeInCallbackRef.current) {
              bargeInCallbackRef.current();
            }
          }
          break;

        case 'auto_send':
          // 백엔드에서 2초 침묵 감지 시 자동 전송 트리거
          console.log('[VoiceStream] 자동 전송 트리거:', data.reason);
          triggerAutoStopRef.current?.();
          break;

        case 'stt_result':
          if (data.text) {
            if (data.is_final) {
              setFinalTranscript((prev) => {
                const newText = prev ? `${prev} ${data.text}` : data.text!;
                return newText;
              });
              setTranscript('');
            } else {
              setTranscript(data.text);
            }
          }
          break;

        case 'ai_response':
          console.log('[VoiceStream] AI 응답:', data.text);
          const response: AIResponse = {
            text: data.text || '',
            intent: data.intent || '',
            suggestedAction: data.suggested_action || '',
          };
          setAiResponse(response);
          latestAiResponseRef.current = response;
          break;

        case 'tts_chunk':
          if (data.audio_base64) {
            console.log(`[VoiceStream] TTS 청크 수신: #${data.chunk_index}, final=${data.is_final}`);
            audioQueueRef.current.push(data.audio_base64);
            playNextAudio();
          }
          break;

        case 'completed':
          console.log('[VoiceStream] 처리 완료:', data.message, 'final_text:', data.final_text);
          setIsProcessing(false);

          if (data.final_text) {
            latestUserTextRef.current = data.final_text;
          }

          // VAD 자동 중지로 처리된 경우 콜백 호출 (결과 포함)
          if (isAutoStoppingRef.current) {
            console.log('[VoiceStream] VAD 자동 처리 완료 - 콜백 호출');
            isAutoStoppingRef.current = false;

            const result: StopRecordingResult = {
              userText: latestUserTextRef.current,
              aiResponse: latestAiResponseRef.current,
            };

            // onAutoStop 콜백을 통해 App에 결과 전달
            if (autoStopCallbackRef.current) {
              autoStopCallbackRef.current(result);
            }
          }

          // EOS로 처리된 경우 (수동 중지)
          if (responseResolverRef.current) {
            responseResolverRef.current({
              userText: latestUserTextRef.current,
              aiResponse: latestAiResponseRef.current,
            });
            responseResolverRef.current = null;
          }
          break;

        case 'error':
          console.error('[VoiceStream] 오류:', data.message);
          setError(data.message || '알 수 없는 오류');
          setIsProcessing(false);

          if (responseResolverRef.current) {
            responseResolverRef.current(null);
            responseResolverRef.current = null;
          }
          break;

        case 'pong':
          // Ping-Pong
          break;
      }
    } catch (e) {
      console.error('[VoiceStream] 메시지 파싱 오류:', e);
    }
  };

  // handleMessage를 ref에 저장 (최신 함수 참조)
  handleMessageRef.current = handleMessage;

  // WebSocket 연결
  const connectWebSocket = useCallback((): Promise<void> => {
    return new Promise((resolve, reject) => {
      const wsUrl = getWsUrl();
      console.log('[VoiceStream] WebSocket 연결 시도:', wsUrl);

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
        console.log('[VoiceStream] WebSocket 열림');
      };

      ws.onmessage = (event) => {
        try {
          const message: ServerMessage = JSON.parse(event.data);
          if (message.type === 'connected' && !isResolved) {
            clearTimeout(timeoutId);
            setIsConnected(true);
            isResolved = true;
            resolve();
          }
        } catch (e) {
          // ignore
        }
        if (handleMessageRef.current) {
          handleMessageRef.current(event);
        }
      };

      ws.onerror = (event) => {
        console.error('[VoiceStream] WebSocket 오류:', event);
        setError('WebSocket 연결 오류');
        clearTimeout(timeoutId);
        if (!isResolved) {
          isResolved = true;
          reject(new Error('WebSocket 연결 오류'));
        }
      };

      ws.onclose = () => {
        console.log('[VoiceStream] WebSocket 닫힘');
        setIsConnected(false);
        wsRef.current = null;
      };
    });
  }, [getWsUrl]);

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

      // 선형 보간
      outputData[i] = inputData[srcIndexFloor] * (1 - t) + inputData[srcIndexCeil] * t;
    }

    return outputData;
  }, []);

  // 오디오 캡처 시작 (16kHz Int16 PCM) - VAD는 백엔드에서 처리
  const startAudioCapture = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,  // 자동 게인 컨트롤 추가
        },
      });

      streamRef.current = stream;
      isAutoStoppingRef.current = false;

      // 브라우저 기본 샘플레이트 사용 (보통 48kHz)
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const actualSampleRate = audioContext.sampleRate;
      console.log('[VoiceStream] 실제 샘플레이트:', actualSampleRate);

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      // 버퍼 크기를 늘려서 더 안정적인 데이터 수집
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN && !isAutoStoppingRef.current) {
          const inputData = e.inputBuffer.getChannelData(0);

          // 16kHz로 리샘플링 (브라우저가 48kHz인 경우)
          const resampledData = resample(inputData, actualSampleRate, 16000);

          // Float32 → Int16 변환 (LINEAR16)
          const pcmData = new Int16Array(resampledData.length);
          for (let i = 0; i < resampledData.length; i++) {
            const s = Math.max(-1, Math.min(1, resampledData[i]));
            pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }

          // 오디오 데이터를 백엔드로 전송 (Silero VAD 처리)
          wsRef.current.send(pcmData.buffer);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      console.log('[VoiceStream] 오디오 캡처 시작 (Silero VAD 사용, 리샘플링:', actualSampleRate, '→ 16000)');
    } catch (err) {
      console.error('[VoiceStream] 마이크 접근 실패:', err);
      setError('마이크 접근 권한이 필요합니다.');
      throw err;
    }
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

    console.log('[VoiceStream] 오디오 캡처 중지');
  }, []);

  // 자동 녹음 중지 (VAD에 의해 호출)
  // 백엔드에서 이미 STT/AI/TTS 처리가 시작되므로, EOS를 보내지 않고 결과만 대기
  // Barge-in을 위해 오디오 캡처는 유지 (TTS 재생 중에도 VAD 감지 필요)
  const triggerAutoStop = useCallback(() => {
    if (isAutoStoppingRef.current) return;
    isAutoStoppingRef.current = true;

    console.log('[VoiceStream] Silero VAD 자동 중지 트리거 (백엔드에서 처리 중, 오디오 캡처 유지)');

    // 오디오 캡처는 유지 (Barge-in 감지를 위해)
    // stopAudioCapture(); <- 제거: TTS 재생 중에도 VAD 결과를 받아야 함
    setIsRecording(false);
    setIsProcessing(true);

    // responseResolver 설정 (completed 메시지 대기용)
    // App.tsx의 processStopRecording 대신 여기서 직접 처리
    latestAiResponseRef.current = null;
    latestUserTextRef.current = '';

    // 타임아웃 설정 (30초)
    setTimeout(() => {
      if (isAutoStoppingRef.current && !responseResolverRef.current) {
        console.log('[VoiceStream] 자동 중지 타임아웃');
        setIsProcessing(false);
      }
    }, 30000);
  }, []);

  // triggerAutoStop을 ref에 저장 (handleMessage에서 참조)
  triggerAutoStopRef.current = triggerAutoStop;

  // 녹음 시작
  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setTranscript('');
      setFinalTranscript('');
      setAiResponse(null);
      setSpeechProb(0);
      setIsSpeaking(false);
      audioQueueRef.current = [];

      // WebSocket 연결 (아직 안 되어 있으면)
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        await connectWebSocket();
      }

      // 오디오 캡처 시작 (이미 캡처 중이면 건너뛰기 - Barge-in/TTS 완료 후 재시작 시)
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        await startAudioCapture();
        console.log('[VoiceStream] 새 오디오 캡처 시작');
      } else {
        console.log('[VoiceStream] 오디오 캡처 이미 활성 - 녹음 상태만 전환');
      }

      // 자동 중지 플래그 리셋
      isAutoStoppingRef.current = false;
      setIsRecording(true);
    } catch (err) {
      console.error('[VoiceStream] 녹음 시작 실패:', err);
      setError('녹음 시작 실패');
      throw err;
    }
  }, [connectWebSocket, startAudioCapture]);

  // 녹음 중지 및 AI 응답 대기
  const stopRecording = useCallback(async (): Promise<StopRecordingResult | null> => {
    return new Promise((resolve) => {
      stopAudioCapture();

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        latestAiResponseRef.current = null;
        latestUserTextRef.current = '';
        responseResolverRef.current = resolve;

        console.log('[VoiceStream] EOS 전송');
        wsRef.current.send('EOS');
        setIsRecording(false);
        setIsProcessing(true);

        // 타임아웃 (30초)
        setTimeout(() => {
          if (responseResolverRef.current) {
            console.log('[VoiceStream] 타임아웃');
            responseResolverRef.current({
              userText: latestUserTextRef.current,
              aiResponse: latestAiResponseRef.current,
            });
            responseResolverRef.current = null;
            setIsProcessing(false);
          }
        }, 30000);
      } else {
        console.log('[VoiceStream] WebSocket이 열려있지 않음');
        setIsRecording(false);
        resolve(null);
      }
    });
  }, [stopAudioCapture]);

  // 연결 해제
  const disconnect = useCallback(() => {
    stopAudioCapture();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsRecording(false);
    setIsConnected(false);
    setIsProcessing(false);
  }, [stopAudioCapture]);

  // VAD 자동 중지 콜백 설정 (결과 포함)
  const setOnAutoStop = useCallback((callback: (result: StopRecordingResult | null) => void) => {
    autoStopCallbackRef.current = callback;
  }, []);

  // TTS 재생 완료 콜백 설정
  const setOnTTSComplete = useCallback((callback: () => void) => {
    ttsCompleteCallbackRef.current = callback;
  }, []);

  // Barge-in 콜백 설정 (TTS 중 사용자가 말하기 시작할 때)
  const setOnBargeIn = useCallback((callback: () => void) => {
    bargeInCallbackRef.current = callback;
  }, []);

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      disconnect();
      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
      }
    };
  }, [disconnect]);

  return {
    isRecording,
    isConnected,
    isProcessing,
    isPlayingTTS,
    isSpeaking,
    speechProb,
    transcript,
    finalTranscript,
    aiResponse,
    error,
    startRecording,
    stopRecording,
    disconnect,
    setOnAutoStop,
    setOnTTSComplete,
    setOnBargeIn,
  };
};

export default useVoiceStream;
