/**
 * 양방향 실시간 음성 스트리밍 훅
 *
 * 기능:
 * - 실시간 STT (VITO WebSocket)
 * - AI 워크플로우 응답
 * - TTS 오디오 스트리밍 재생
 *
 * 사용법:
 * const {
 *   isRecording,
 *   isConnected,
 *   transcript,
 *   aiResponse,
 *   startRecording,
 *   stopRecording,
 * } = useVoiceStream(sessionId);
 */

import { useState, useRef, useCallback, useEffect } from 'react';

// 서버 메시지 타입
interface ServerMessage {
  type: 'connected' | 'stt_result' | 'ai_response' | 'tts_chunk' | 'completed' | 'error' | 'pong';
  data: {
    // connected
    session_id?: string;
    message?: string;
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
  };
  timestamp: number;
}

interface AIResponse {
  text: string;
  intent: string;
  suggestedAction: string;
}

// stopRecording 반환 타입
interface StopRecordingResult {
  userText: string;        // 사용자가 말한 텍스트
  aiResponse: AIResponse | null;  // AI 응답
}

interface UseVoiceStreamReturn {
  isRecording: boolean;
  isConnected: boolean;
  isProcessing: boolean;
  isPlayingTTS: boolean;       // TTS 재생 중인지
  transcript: string;          // 현재 인식 중인 텍스트 (부분)
  finalTranscript: string;     // 확정된 텍스트
  aiResponse: AIResponse | null;
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<StopRecordingResult | null>;
  disconnect: () => void;
  setOnAutoStop: (callback: () => void) => void;  // VAD 자동 중지 콜백 설정
  setOnTTSComplete: (callback: () => void) => void;  // TTS 재생 완료 콜백
  setOnBargeIn: (callback: () => void) => void;  // Barge-in 콜백 (TTS 중 사용자 말하기)
}

export const useVoiceStream = (sessionId: string): UseVoiceStreamReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPlayingTTS, setIsPlayingTTS] = useState(false);  // TTS 재생 상태
  const [transcript, setTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [aiResponse, setAiResponse] = useState<AIResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // VAD (Voice Activity Detection) - 2초 침묵 감지
  const VAD_SILENCE_THRESHOLD = 0.02;  // 볼륨 임계값 (0~1) - 배경 소음 고려하여 상향
  const VAD_SILENCE_DURATION = 2000;   // 침묵 지속 시간 (ms)
  const BARGE_IN_THRESHOLD = 0.025;    // Barge-in 임계값 (더 민감하게)
  const silenceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasSpokenRef = useRef<boolean>(false);  // 한 번이라도 말했는지
  const isAutoStoppingRef = useRef<boolean>(false);  // 자동 중지 중인지

  // TTS 재생용
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const ttsCompleteCallbackRef = useRef<(() => void) | null>(null);  // TTS 완료 콜백
  const bargeInCallbackRef = useRef<(() => void) | null>(null);  // Barge-in 콜백
  const hasTTSStartedRef = useRef<boolean>(false);  // TTS가 시작되었는지 (완료 감지용)

  // Barge-in 감지용 마이크 (TTS 재생 중 음성 감지)
  const bargeInStreamRef = useRef<MediaStream | null>(null);
  const bargeInContextRef = useRef<AudioContext | null>(null);
  const bargeInProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const bargeInSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const isBargeInActiveRef = useRef<boolean>(false);  // Barge-in 감지 활성화 상태

  // Promise resolver (stopRecording에서 결과 대기용)
  const responseResolverRef = useRef<((result: StopRecordingResult | null) => void) | null>(null);

  // AI 응답 저장용 ref (클로저 문제 해결)
  const latestAiResponseRef = useRef<AIResponse | null>(null);

  // 사용자 텍스트 저장용 ref (서버에서 받은 final_text)
  const latestUserTextRef = useRef<string>('');

  // handleMessage ref (클로저 문제 해결)
  const handleMessageRef = useRef<((event: MessageEvent) => void) | null>(null);

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

  // Barge-in 감지 중지
  const stopBargeInDetection = useCallback(() => {
    isBargeInActiveRef.current = false;

    if (bargeInProcessorRef.current) {
      bargeInProcessorRef.current.disconnect();
      bargeInProcessorRef.current = null;
    }

    if (bargeInSourceRef.current) {
      bargeInSourceRef.current.disconnect();
      bargeInSourceRef.current = null;
    }

    if (bargeInContextRef.current) {
      bargeInContextRef.current.close();
      bargeInContextRef.current = null;
    }

    if (bargeInStreamRef.current) {
      bargeInStreamRef.current.getTracks().forEach((track) => track.stop());
      bargeInStreamRef.current = null;
    }
  }, []);

  // Barge-in 감지 시작 (TTS 재생 중 사용자 음성 감지)
  const startBargeInDetection = useCallback(async () => {
    try {
      // 이미 활성화되어 있으면 스킵
      if (isBargeInActiveRef.current) return;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      bargeInStreamRef.current = stream;
      isBargeInActiveRef.current = true;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      bargeInContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      bargeInSourceRef.current = source;

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      bargeInProcessorRef.current = processor;

      // 음성 감지 카운터 (슬라이딩 윈도우 방식)
      let voiceDetectedCount = 0;
      let totalSamples = 0;
      const WINDOW_SIZE = 5;  // 최근 5개 샘플 중
      const MIN_VOICE_COUNT = 2;  // 2개 이상 음성이면 Barge-in

      processor.onaudioprocess = (e) => {
        if (!isBargeInActiveRef.current) {
          return;
        }

        if (!isPlayingRef.current) {
          // TTS가 끝났으면 Barge-in 감지 중지
          return;
        }

        const inputData = e.inputBuffer.getChannelData(0);

        // RMS 계산
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
          sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);

        totalSamples++;

        // Barge-in 감지 (슬라이딩 윈도우)
        if (rms > BARGE_IN_THRESHOLD) {
          voiceDetectedCount++;
          console.log(`[Barge-in] 음성 감지! RMS: ${rms.toFixed(4)}, count: ${voiceDetectedCount}`);

          if (voiceDetectedCount >= MIN_VOICE_COUNT) {
            console.log('[VoiceStream] Barge-in 감지! RMS:', rms.toFixed(4));

            // TTS 중지
            stopTTS();

            // Barge-in 감지 중지
            stopBargeInDetection();

            // Barge-in 콜백 호출 (녹음 시작)
            if (bargeInCallbackRef.current) {
              bargeInCallbackRef.current();
            }
          }
        }

        // 윈도우 크기마다 카운터 감소 (슬라이딩)
        if (totalSamples % WINDOW_SIZE === 0 && voiceDetectedCount > 0) {
          voiceDetectedCount = Math.max(0, voiceDetectedCount - 1);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      console.log('[VoiceStream] Barge-in 감지 시작');
    } catch (err) {
      console.error('[VoiceStream] Barge-in 감지 시작 실패:', err);
    }
  }, [stopTTS, stopBargeInDetection]);

  // TTS 오디오 재생 (큐 기반)
  const playNextAudio = useCallback(() => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      // 큐가 비어있고 재생 중이 아니면 TTS 완료
      if (!isPlayingRef.current && audioQueueRef.current.length === 0 && hasTTSStartedRef.current) {
        console.log('[VoiceStream] TTS 재생 완료');
        setIsPlayingTTS(false);
        hasTTSStartedRef.current = false;

        // Barge-in 감지 중지
        stopBargeInDetection();

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

    // 첫 TTS 청크 재생 시 Barge-in 감지 시작
    if (!isBargeInActiveRef.current) {
      startBargeInDetection();
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
  }, [base64ToBlob, startBargeInDetection, stopBargeInDetection]);

  // WebSocket 메시지 핸들러 (직접 정의, useCallback 없이)
  const handleMessage = (event: MessageEvent) => {
    try {
      const message: ServerMessage = JSON.parse(event.data);
      const { type, data } = message;

      console.log('[VoiceStream] 메시지 수신:', type, data);

      switch (type) {
        case 'connected':
          console.log('[VoiceStream] 연결 완료:', data.message);
          setIsConnected(true);
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
          latestAiResponseRef.current = response;  // ref에도 저장
          console.log('[VoiceStream] latestAiResponseRef 저장됨:', response);
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

          // 사용자 텍스트 저장 (서버에서 받은 final_text)
          if (data.final_text) {
            latestUserTextRef.current = data.final_text;
          }

          console.log('[VoiceStream] resolver 호출 전 상태:', {
            userText: latestUserTextRef.current,
            aiResponse: latestAiResponseRef.current,
            hasResolver: !!responseResolverRef.current,
          });

          // stopRecording의 Promise 해결 (ref 사용으로 클로저 문제 해결)
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
        // 첫 connected 메시지에서 resolve
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
        // ref를 통해 최신 handleMessage 호출
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

  // 자동 녹음 중지 (VAD에 의해 호출)
  const triggerAutoStop = useCallback(() => {
    if (isAutoStoppingRef.current) return;
    isAutoStoppingRef.current = true;

    // onAutoStop 콜백을 통해 App에 알림
    if (autoStopCallbackRef.current) {
      autoStopCallbackRef.current();
    }
  }, []);

  // 자동 중지 콜백 ref
  const autoStopCallbackRef = useRef<(() => void) | null>(null);

  // 오디오 캡처 시작 (16kHz Int16 PCM) + VAD
  const startAudioCapture = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      streamRef.current = stream;

      // VAD 상태 초기화
      hasSpokenRef.current = false;
      isAutoStoppingRef.current = false;
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
        silenceTimeoutRef.current = null;
      }

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN && !isAutoStoppingRef.current) {
          const inputData = e.inputBuffer.getChannelData(0);

          // RMS (볼륨) 계산 for VAD
          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += inputData[i] * inputData[i];
          }
          const rms = Math.sqrt(sum / inputData.length);

          // VAD 로직: 말한 후 2초간 침묵 시 자동 전송
          if (rms > VAD_SILENCE_THRESHOLD) {
            // 말하는 중 → 타이머 리셋
            hasSpokenRef.current = true;
            if (silenceTimeoutRef.current) {
              clearTimeout(silenceTimeoutRef.current);
              silenceTimeoutRef.current = null;
            }
          } else if (hasSpokenRef.current && !silenceTimeoutRef.current) {
            // 한 번 말한 후 침묵 시작 → 타이머 설정
            silenceTimeoutRef.current = setTimeout(() => {
              triggerAutoStop();
            }, VAD_SILENCE_DURATION);
          }

          // Float32 → Int16 변환 (LINEAR16)
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }

          wsRef.current.send(pcmData.buffer);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      console.log('[VoiceStream] 오디오 캡처 시작 (VAD 활성화)');
    } catch (err) {
      console.error('[VoiceStream] 마이크 접근 실패:', err);
      setError('마이크 접근 권한이 필요합니다.');
      throw err;
    }
  }, [triggerAutoStop]);

  // 오디오 캡처 중지
  const stopAudioCapture = useCallback(() => {
    // VAD 타이머 정리
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current);
      silenceTimeoutRef.current = null;
    }

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

  // 녹음 시작
  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setTranscript('');
      setFinalTranscript('');
      setAiResponse(null);
      audioQueueRef.current = [];

      // WebSocket 연결 (아직 안 되어 있으면)
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        await connectWebSocket();
      }

      // 오디오 캡처 시작
      await startAudioCapture();

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
        // ref 초기화 (EOS 전송 전에!)
        latestAiResponseRef.current = null;
        latestUserTextRef.current = '';

        // 결과 완료 대기 resolver 설정 (EOS 전송 전에!)
        responseResolverRef.current = resolve;

        // EOS 전송 → 서버에서 AI 응답 처리
        console.log('[VoiceStream] EOS 전송');
        wsRef.current.send('EOS');
        setIsRecording(false);
        setIsProcessing(true);

        // 타임아웃 (30초)
        setTimeout(() => {
          if (responseResolverRef.current) {
            console.log('[VoiceStream] 타임아웃 - 현재 상태:', {
              userText: latestUserTextRef.current,
              aiResponse: latestAiResponseRef.current,
            });
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

  // VAD 자동 중지 콜백 설정
  const setOnAutoStop = useCallback((callback: () => void) => {
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
      stopBargeInDetection();
      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
      }
    };
  }, [disconnect, stopBargeInDetection]);

  return {
    isRecording,
    isConnected,
    isProcessing,
    isPlayingTTS,
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
