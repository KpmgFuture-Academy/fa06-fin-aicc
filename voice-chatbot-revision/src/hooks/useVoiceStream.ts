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

// ============================================================
// Barge-in 상수 정의
// ============================================================
const BARGE_IN_GUARD_TIME_MS = 120;  // TTS 시작 후 이 시간 동안은 Barge-in 무시 (피드백 방지)
const BARGE_IN_STRONG_PROB = 0.90;   // 강한 발화 임계값
const BARGE_IN_STRONG_DURATION_MS = 120;  // 강한 발화 지속 시간
const BARGE_IN_WEAK_PROB = 0.80;     // 약한 발화 임계값
const BARGE_IN_WEAK_DURATION_MS = 200;    // 약한 발화 지속 시간

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
    handover_status?: string | null;  // 핸드오버 상태
    is_human_required_flow?: boolean;  // HUMAN_REQUIRED 플로우 여부
    is_session_end?: boolean;  // 세션 종료 여부
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
  handoverStatus?: string | null;  // 핸드오버 상태 (pending, accepted, declined, timeout)
  isHumanRequiredFlow?: boolean;  // HUMAN_REQUIRED 플로우 진입 여부
  isSessionEnd?: boolean;  // 세션 종료 여부 (불명확 응답/도메인 외 질문 3회 이상 시 true)
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
  stopTTS: () => void;  // TTS 재생 중지 (HANDOVER 등에서 사용)
  setOnAutoStop: (callback: (result: StopRecordingResult | null) => void) => void;  // VAD 자동 중지 콜백 (결과 포함)
  setOnTTSComplete: (callback: () => void) => void;  // TTS 재생 완료 콜백
  setOnBargeIn: (callback: () => void) => void;  // Barge-in 콜백 (TTS 중 사용자 말하기)
  setExternalTTSPlaying: (playing: boolean) => void;  // 외부 TTS 재생 상태 설정 (첫 인사 등)
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

  // sessionId를 ref로 관리하여 최신 값 보장 (closure 문제 방지)
  const sessionIdRef = useRef<string>(sessionId);
  sessionIdRef.current = sessionId;

  // 자동 중지 관련 ref
  const isAutoStoppingRef = useRef<boolean>(false);

  // TTS 재생용
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const ttsCompleteCallbackRef = useRef<(() => void) | null>(null);  // TTS 완료 콜백
  const bargeInCallbackRef = useRef<(() => void) | null>(null);  // Barge-in 콜백
  const hasTTSStartedRef = useRef<boolean>(false);  // TTS가 시작되었는지 (완료 감지용)

  // Barge-in 관련 refs
  const ttsStartTimeRef = useRef<number>(0);  // TTS 시작 시점 (ms)
  const speechStartTimeRef = useRef<number>(0);  // 연속 발화 시작 시점 (ms)
  const consecutiveSpeechRef = useRef<boolean>(false);  // 연속 발화 감지 여부

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

  // WebSocket URL 생성 (ref 사용으로 항상 최신 sessionId 보장)
  const getWsUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const currentSessionId = sessionIdRef.current;
    console.log('[VoiceStream] getWsUrl - 사용할 sessionId:', currentSessionId);
    return `${protocol}//${window.location.host}/api/v1/voice/streaming/${currentSessionId}`;
  }, []);

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
    console.log('[VoiceStream] stopTTS 호출');
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.currentTime = 0;
    }
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    hasTTSStartedRef.current = false;
    setIsPlayingTTS(false);

    // Barge-in refs 리셋
    ttsStartTimeRef.current = 0;
    speechStartTimeRef.current = 0;
    consecutiveSpeechRef.current = false;
  }, []);

  // TTS 오디오 재생 (큐 기반)
  const playNextAudio = useCallback(() => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      // 큐가 비어있고 재생 중이 아니면 TTS 완료
      if (!isPlayingRef.current && audioQueueRef.current.length === 0 && hasTTSStartedRef.current) {
        console.log('[VoiceStream] TTS 재생 완료');
        setIsPlayingTTS(false);
        hasTTSStartedRef.current = false;

        // Barge-in refs 리셋
        ttsStartTimeRef.current = 0;
        speechStartTimeRef.current = 0;
        consecutiveSpeechRef.current = false;

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

    // Barge-in: TTS 시작 시점 기록 (첫 청크만)
    if (ttsStartTimeRef.current === 0) {
      ttsStartTimeRef.current = Date.now();
      console.log('[VoiceStream] TTS 시작 시점 기록:', ttsStartTimeRef.current);
    }

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
        // 다음 청크가 있으면 isPlayingRef를 true로 유지 (Barge-in 감지 유지)
        // 다음 청크가 없으면 false로 설정하여 TTS 완료 처리
        if (audioQueueRef.current.length === 0) {
          isPlayingRef.current = false;
        }
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

          // ============================================================
          // Barge-in 로직: TTS 재생 중 사용자 발화 감지 시 TTS 중단
          // ============================================================
          // 디버깅: TTS 재생 중 모든 VAD 결과 로깅 (prob > 0.3인 경우만)
          if (isPlayingRef.current && data.speech_prob && data.speech_prob > 0.3) {
            console.log('[VoiceStream] TTS 중 VAD - prob:', data.speech_prob, 'is_speech:', data.is_speech, 'ttsStartTime:', ttsStartTimeRef.current);
          }
          if (isPlayingRef.current && ttsStartTimeRef.current > 0) {
            const now = Date.now();
            const elapsedSinceTTSStart = now - ttsStartTimeRef.current;

            // Guard time (120ms) 이전은 무시 (TTS 피드백 방지)
            if (elapsedSinceTTSStart < BARGE_IN_GUARD_TIME_MS) {
              break;
            }

            const speechProb = data.speech_prob ?? 0;
            const isSpeech = data.is_speech ?? false;

            // speech_prob이 최소 임계값(BARGE_IN_WEAK_PROB) 이상일 때만 발화로 인정
            // AEC 필터링 후 낮은 prob으로 is_speech=true가 되는 경우 제외
            if (isSpeech && speechProb >= BARGE_IN_WEAK_PROB) {
              // 연속 발화 시작 시점 기록
              if (!consecutiveSpeechRef.current) {
                consecutiveSpeechRef.current = true;
                speechStartTimeRef.current = now;
                console.log('[VoiceStream] Barge-in: 발화 시작 감지, prob:', speechProb);
              }

              const speechDuration = now - speechStartTimeRef.current;

              // 강한 발화 조건: 90% 이상 확률로 120ms 이상 지속
              const isStrongSpeech = speechProb >= BARGE_IN_STRONG_PROB && speechDuration >= BARGE_IN_STRONG_DURATION_MS;
              // 약한 발화 조건: 80% 이상 확률로 200ms 이상 지속
              const isWeakSpeech = speechProb >= BARGE_IN_WEAK_PROB && speechDuration >= BARGE_IN_WEAK_DURATION_MS;

              if (isStrongSpeech || isWeakSpeech) {
                console.log(`[VoiceStream] Barge-in 트리거! prob: ${speechProb}, duration: ${speechDuration}ms, type: ${isStrongSpeech ? 'strong' : 'weak'}`);
                stopTTS();
                bargeInCallbackRef.current?.();
                consecutiveSpeechRef.current = false;
              }
            } else {
              // 발화 종료 시 연속 발화 리셋
              if (consecutiveSpeechRef.current) {
                console.log('[VoiceStream] Barge-in: 발화 종료, 연속 감지 리셋');
                consecutiveSpeechRef.current = false;
                speechStartTimeRef.current = 0;
              }
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
          console.log('[VoiceStream] AI 응답:', data.text, 'handover_status:', data.handover_status, 'is_human_required_flow:', data.is_human_required_flow, 'is_session_end:', data.is_session_end);
          const response: AIResponse = {
            text: data.text || '',
            intent: data.intent || '',
            suggestedAction: data.suggested_action || '',
            handoverStatus: data.handover_status || null,  // 핸드오버 상태 추가
            isHumanRequiredFlow: data.is_human_required_flow || false,  // HUMAN_REQUIRED 플로우 여부
            isSessionEnd: data.is_session_end || false,  // 세션 종료 여부
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

          // VAD 자동 중지로 처리된 경우 또는 aiResponse가 있는 경우 콜백 호출
          // (TTS 완료 후 startRecording이 먼저 호출되어 isAutoStoppingRef가 리셋될 수 있음)
          const hasAiResponse = latestAiResponseRef.current !== null;
          const hasUserText = latestUserTextRef.current.trim() !== '';

          if (isAutoStoppingRef.current || (hasAiResponse && hasUserText && !responseResolverRef.current)) {
            console.log('[VoiceStream] VAD 자동 처리 완료 - 콜백 호출, isAutoStopping:', isAutoStoppingRef.current, 'hasAiResponse:', hasAiResponse);
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
          const errorMsg = data.message || (data as Record<string, unknown>).error as string || '알 수 없는 오류';
          console.error('[VoiceStream] 오류:', errorMsg);
          setError(errorMsg);
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
        // Barge-in 지원: TTS 재생 중에도 VAD 감지를 위해 오디오 전송 유지
        // AEC(에코 캔슬링)가 활성화되어 있으므로 TTS 피드백은 필터링됨
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
  // 오디오 캡처는 유지하지만, TTS 재생 중에는 전송 중지 (피드백 방지)
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

  // 외부 TTS 재생 상태 설정 (첫 인사 등 외부에서 재생하는 TTS)
  // Barge-in 감지를 위해 isPlayingRef와 ttsStartTimeRef를 설정
  const setExternalTTSPlaying = useCallback((playing: boolean) => {
    console.log('[VoiceStream] 외부 TTS 재생 상태 설정:', playing);
    isPlayingRef.current = playing;
    setIsPlayingTTS(playing);
    if (playing) {
      ttsStartTimeRef.current = Date.now();
      hasTTSStartedRef.current = true;
      consecutiveSpeechRef.current = false;
      speechStartTimeRef.current = 0;
    } else {
      ttsStartTimeRef.current = 0;
      hasTTSStartedRef.current = false;
      consecutiveSpeechRef.current = false;
      speechStartTimeRef.current = 0;
    }
  }, []);

  // sessionId 변경 시 기존 WebSocket 연결 해제 (세션 ID 동기화 문제 방지)
  const prevSessionIdRef = useRef<string>(sessionId);
  useEffect(() => {
    if (prevSessionIdRef.current !== sessionId) {
      console.log(`[VoiceStream] sessionId 변경 감지: ${prevSessionIdRef.current} → ${sessionId}, 기존 연결 해제`);
      disconnect();
      prevSessionIdRef.current = sessionId;
    }
  }, [sessionId, disconnect]);

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
    stopTTS,
    setOnAutoStop,
    setOnTTSComplete,
    setOnBargeIn,
    setExternalTTSPlaying,
  };
};

export default useVoiceStream;
