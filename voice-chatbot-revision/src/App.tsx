import { useState, useCallback, useRef, useEffect } from 'react';
import VoiceButton from './components/VoiceButton';
import ChatMessage, { Message } from './components/ChatMessage';
import { useVoiceStream } from './hooks/useVoiceStream';
import { useVoiceRecording, VoiceRecordingResult } from './hooks/useVoiceRecording';
import { voiceApi, getOrCreateSessionId, resetSessionId, formatSessionIdForDisplay, HandoverResponse } from './services/api';
import './App.css';

// 자동 인사 메시지 설정
const WELCOME_MESSAGE = "안녕하세요 고객님, 카드 상담 보이스봇에 연결되었습니다. 무엇을 도와 드릴까요? 음성 상담 및 텍스트 상담 모두 가능합니다.";
const WELCOME_DELAY_MS = 2000; // 2초 후 인사

// 핸드오버 관련 설정
const HANDOVER_POLL_INTERVAL_MS = 2000; // 2초마다 상담사 수락 여부 폴링
const HANDOVER_TIMEOUT_MS = 60000; // 60초 타임아웃 (실제로는 필요시 조정)
const HANDOVER_WAIT_TIME_MESSAGE = "현재 모든 상담사가 상담 중입니다. 예상 대기 시간은 약 10분입니다.";

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState(() => getOrCreateSessionId());
  const [_handoverData, setHandoverData] = useState<HandoverResponse | null>(null);
  void _handoverData;  // 미사용 (향후 확장용)
  const [isHandoverMode, setIsHandoverMode] = useState(false);  // 상담원 연결 모드 (실제 상담 중)
  const [_isHandoverLoading, setIsHandoverLoading] = useState(false);  // 상담원 연결 로딩 상태 (미사용)
  void _isHandoverLoading;
  const [isWaitingForAgent, setIsWaitingForAgent] = useState(false);  // 상담사 수락 대기 중
  const [_handoverTimeoutReached, setHandoverTimeoutReached] = useState(false);  // 타임아웃 도달 여부 (미사용, 향후 확장용)
  void _handoverTimeoutReached;
  const handoverPollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const handoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startHandoverPollingRef = useRef<(() => void) | null>(null);  // 클로저 문제 해결용
  const handoverAcceptedProcessingRef = useRef<boolean>(false);  // accepted 상태 처리 중복 방지
  const [textInput, setTextInput] = useState('');  // 텍스트 입력 상태
  const [isTextSending, setIsTextSending] = useState(false);  // 텍스트 전송 중 상태
  const [hasGreeted, setHasGreeted] = useState(false);  // 인사 메시지 표시 여부
  const [isRecordingMode, setIsRecordingMode] = useState(true);  // true: 녹음 모드, false: 실시간 스트리밍 모드
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textInputRef = useRef<HTMLInputElement>(null);
  const isHandoverModeRef = useRef(false);  // 클로저 문제 해결용 ref
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastMessageIdRef = useRef<number>(0);  // 마지막 메시지 ID (폴링용)
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isConfirmingHandoverRef = useRef(false);  // confirmHandover 중복 호출 방지용

  // 양방향 스트리밍 훅 사용 (STT + AI + TTS 통합)
  const {
    isRecording: isStreamRecording,
    isConnected: _isConnected,
    isProcessing: isStreamProcessing,
    isPlayingTTS,
    transcript,
    finalTranscript,
    error: _sttError,
    startRecording: startStreamRecording,
    stopRecording: stopStreamRecording,
    stopTTS: _stopTTS,
    setOnAutoStop,
    setOnTTSComplete,
    setOnBargeIn,
  } = useVoiceStream(sessionId);
  // Suppress unused variable warnings
  void _isConnected;
  void _sttError;
  void _stopTTS;

  // 녹음 모드 훅 (디버깅용)
  const {
    isRecording: isRecordRecording,
    isProcessing: isRecordProcessing,
    error: _recordError,
    recordingTime,
    startRecording: startRecordRecording,
    stopRecording: stopRecordRecording,
  } = useVoiceRecording(sessionId);
  void _recordError;

  // 현재 모드에 따른 상태 통합
  const isRecording = isRecordingMode ? isRecordRecording : isStreamRecording;
  const isProcessing = isRecordingMode ? isRecordProcessing : isStreamProcessing;

  // 통합 녹음 시작/중지 함수
  const startRecording = isRecordingMode ? startRecordRecording : startStreamRecording;
  const stopRecording = isRecordingMode ? stopRecordRecording : stopStreamRecording;

  // 연속 대화 모드 (첫 녹음 후 활성화)
  const [isContinuousMode, setIsContinuousMode] = useState(false);

  // 연속 빈 입력 카운터 (무한 루프 방지)
  const emptyInputCountRef = useRef<number>(0);
  const MAX_EMPTY_INPUTS = 2;  // 연속 2회 빈 입력 시 연속 대화 일시 중지

  // 현재 표시할 텍스트 (확정 + 부분)
  const currentTranscript = finalTranscript + (transcript ? ` ${transcript}` : '');

  // isHandoverMode가 변경될 때 ref도 업데이트 (클로저 문제 해결)
  useEffect(() => {
    isHandoverModeRef.current = isHandoverMode;
    console.log('[App] isHandoverMode 변경:', isHandoverMode);
  }, [isHandoverMode]);

  // 메시지 추가 시 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentTranscript]);

  // base64 → Blob 변환
  const base64ToBlob = (base64: string, mimeType: string): Blob => {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
  };

  // 자동 인사 메시지 (화면 로드 2초 후)
  useEffect(() => {
    if (hasGreeted) return;

    const timer = setTimeout(async () => {
      // 인사 메시지 추가
      const greetingMessage: Message = {
        id: `msg_${Date.now()}_greeting`,
        role: 'assistant',
        content: WELCOME_MESSAGE,
        timestamp: new Date(),
      };
      setMessages([greetingMessage]);
      setHasGreeted(true);

      // TTS 재생
      try {
        const ttsResponse = await voiceApi.requestTTS(WELCOME_MESSAGE);
        if (ttsResponse.audio_base64) {
          const audioBlob = base64ToBlob(ttsResponse.audio_base64, 'audio/mp3');
          const audioUrl = URL.createObjectURL(audioBlob);
          if (audioRef.current) {
            audioRef.current.src = audioUrl;
            audioRef.current.play();
          }
        }
      } catch (err) {
        console.warn('인사 TTS 재생 실패:', err);
      }
    }, WELCOME_DELAY_MS);

    return () => clearTimeout(timer);
  }, [hasGreeted]);

  // TTS 오디오 재생
  const playAudio = useCallback((base64Audio: string) => {
    try {
      const audioBlob = base64ToBlob(base64Audio, 'audio/mp3');
      const audioUrl = URL.createObjectURL(audioBlob);

      if (audioRef.current) {
        audioRef.current.src = audioUrl;
        audioRef.current.play();
      }
    } catch (err) {
      console.error('오디오 재생 실패:', err);
    }
  }, []);

  // 상담원 메시지 폴링 (이관 모드일 때만)
  // 이미 처리한 메시지 ID를 추적하는 Set (중복 방지)
  const processedAgentMessageIdsRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!isHandoverMode) return;

    // 폴링 중복 실행 방지 플래그
    let isPolling = false;

    const pollAgentMessages = async () => {
      // 이미 폴링 중이면 스킵
      if (isPolling) return;
      isPolling = true;

      try {
        const params = new URLSearchParams();
        if (lastMessageIdRef.current > 0) {
          params.append('after_id', lastMessageIdRef.current.toString());
        }
        params.append('after_handover', 'true');

        const response = await fetch(`/api/v1/sessions/${sessionId}/messages?${params.toString()}`);
        if (!response.ok) return;

        const newMessages = await response.json();

        if (newMessages.length > 0) {
          // 마지막 메시지 ID 먼저 업데이트 (다음 폴링에서 중복 방지)
          const maxId = Math.max(...newMessages.map((m: any) => m.id));
          lastMessageIdRef.current = maxId;

          // 상담원 메시지만 필터링 (role === 'assistant')
          const agentMessages = newMessages.filter((m: any) => m.role === 'assistant');

          // 아직 처리하지 않은 메시지만 필터링
          const unprocessedMessages = agentMessages.filter(
            (msg: any) => !processedAgentMessageIdsRef.current.has(msg.id)
          );

          if (unprocessedMessages.length === 0) return;

          // 처리할 메시지 ID들을 먼저 등록 (중복 처리 방지)
          unprocessedMessages.forEach((msg: any) => {
            processedAgentMessageIdsRef.current.add(msg.id);
          });

          // 새 메시지들을 한 번에 추가 (배치 처리)
          const newChatMessages: Message[] = unprocessedMessages.map((msg: any) => ({
            id: `msg_agent_${msg.id}`,
            role: 'assistant' as const,
            content: msg.message,
            timestamp: new Date(msg.created_at),
            isAgent: true,
          }));

          setMessages((prev) => {
            // 기존 메시지 ID 집합
            const existingIds = new Set(prev.map((m) => m.id));
            // 중복되지 않은 새 메시지만 필터링
            const uniqueNewMessages = newChatMessages.filter((m) => !existingIds.has(m.id));
            if (uniqueNewMessages.length === 0) return prev;
            return [...prev, ...uniqueNewMessages];
          });

          // TTS 재생 (첫 번째 메시지만, 순차적으로)
          for (const msg of unprocessedMessages) {
            try {
              const ttsResponse = await fetch('/api/v1/voice/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: msg.message }),
              });

              if (ttsResponse.ok) {
                const ttsData = await ttsResponse.json();
                if (ttsData.audio_base64) {
                  playAudio(ttsData.audio_base64);
                }
              }
            } catch (ttsErr) {
              console.warn('TTS 실패:', ttsErr);
            }
          }
        }
      } catch (err) {
        console.error('상담원 메시지 폴링 실패:', err);
      } finally {
        isPolling = false;
      }
    };

    // 2초마다 폴링
    pollingIntervalRef.current = setInterval(pollAgentMessages, 2000);
    pollAgentMessages(); // 즉시 한 번 실행

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isHandoverMode, sessionId, playAudio]);

  // 녹음 중지 및 메시지 처리 (공통 로직)
  const processStopRecording = useCallback(async () => {
    console.log('[App] ========== processStopRecording 시작 ==========');
    console.log('[App] isHandoverMode:', isHandoverMode, 'isRecordingMode:', isRecordingMode, 'isWaitingForAgent:', isWaitingForAgent);
    const result = await stopRecording();
    console.log('[App] stopRecording 결과 - result 존재:', !!result);
    if (result) {
      console.log('[App] stopRecording 결과 - userText:', result.userText);
      console.log('[App] stopRecording 결과 - aiResponse:', JSON.stringify(result.aiResponse, null, 2));
      console.log('[App] stopRecording 결과 - audioBase64 존재:', !!result.audioBase64, ', 길이:', result.audioBase64?.length || 0);
    }

    if (result) {
      // 사용자 메시지 추가 (서버에서 받은 final_text 사용)
      if (result.userText?.trim()) {
        console.log('[App] 사용자 메시지 추가:', result.userText);
        // 성공적인 입력 시 빈 입력 카운터 초기화
        emptyInputCountRef.current = 0;

        const userMessageContent = result.userText.trim();
        const userMessage: Message = {
          id: `msg_${Date.now()}_user_${Math.random().toString(36).substring(2, 11)}`,
          role: 'user',
          content: userMessageContent,
          timestamp: new Date(),
          isVoice: true,
        };

        // 중복 메시지 방지: 최근 5개 메시지 중 동일 content가 있으면 추가하지 않음
        setMessages((prev) => {
          const recentMessages = prev.slice(-5);
          const isDuplicate = recentMessages.some(
            (m) => m.role === 'user' && m.content === userMessageContent
          );
          if (isDuplicate) {
            console.log('[App] 중복 사용자 메시지 무시:', userMessageContent);
            return prev;
          }
          return [...prev, userMessage];
        });

        // 이관 모드일 때: AI 응답 무시하고 상담원에게 메시지 전송
        if (isHandoverMode) {
          console.log('[App] 이관 모드 - 상담원에게 메시지 전송:', result.userText);
          try {
            await voiceApi.sendCustomerMessage(sessionId, result.userText.trim());
            console.log('[App] 상담원에게 메시지 전송 완료');
          } catch (err) {
            console.error('[App] 상담원에게 메시지 전송 실패:', err);
          }
          return; // AI 응답 처리 건너뛰기
        }
      } else {
        console.log('[App] userText가 비어있음');
      }

      // AI 응답 메시지 추가 (이관 모드가 아닐 때만)
      if (!isHandoverMode && result.aiResponse?.text) {
        // 디버그: AI 응답 전체 내용 출력
        console.log('[App] 녹음 모드 - AI 응답 전체:', JSON.stringify(result.aiResponse, null, 2));
        console.log('[App] 녹음 모드 - audioBase64 존재 여부:', !!result.audioBase64, ', 길이:', result.audioBase64?.length || 0);

        // HANDOVER 감지 (녹음 모드에서)
        const isHandoverSuggested =
          result.aiResponse.suggestedAction === 'HANDOVER' ||
          result.aiResponse.suggestedAction === 'handover' ||
          result.aiResponse.text.includes('상담사에게 연결해 드리겠습니다') ||
          result.aiResponse.text.includes('상담원에게 연결');

        console.log('[App] 녹음 모드 AI 응답 - suggestedAction:', result.aiResponse.suggestedAction, ', handoverStatus:', result.aiResponse.handoverStatus, ', isHandoverSuggested:', isHandoverSuggested);

        // handover_status가 pending이면 상담사 수락 대기 폴링 시작
        // 안내 메시지는 백엔드(waiting_agent)에서 이미 ai_message에 포함됨
        console.log('[App] 녹음 모드 - isWaitingForAgent 상태:', isWaitingForAgent);
        if (result.aiResponse.handoverStatus === 'pending' && !isWaitingForAgent) {
          console.log('[App] 녹음 모드 - handover_status=pending 감지 - 상담사 수락 대기 폴링 시작');
          setIsWaitingForAgent(true);
          setHandoverTimeoutReached(false);
          startHandoverPolling();
        }

        if (isHandoverSuggested) {
          console.log('[App] 녹음 모드 - HANDOVER 감지, 메시지 표시 및 TTS 재생 시작');
          console.log('[App] 녹음 모드 - 표시할 메시지:', result.aiResponse.text);

          // AI 응답 메시지만 표시 (고객에게 동의 요청)
          // 고객이 "네"라고 응답하면 백엔드의 consent_check_node가 처리함
          const aiMessageContent = result.aiResponse.text;
          const aiMessage: Message = {
            id: `msg_${Date.now()}_assistant_${Math.random().toString(36).substring(2, 11)}`,
            role: 'assistant',
            content: aiMessageContent,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, aiMessage]);

          // AI 응답 TTS 재생 (녹음 모드에서는 수동 재생)
          const recordResult = result as VoiceRecordingResult;
          console.log('[App] 녹음 모드 - TTS 재생 시도, audioBase64 존재:', !!recordResult.audioBase64);
          if (recordResult.audioBase64) {
            console.log('[App] 녹음 모드 - TTS 재생 시작, 오디오 길이:', recordResult.audioBase64.length);
            playAudio(recordResult.audioBase64);
          } else {
            console.warn('[App] 녹음 모드 - audioBase64가 없어 TTS 재생 불가');
          }

          // 고객이 "네"라고 응답할 때까지 대기
          // 다음 메시지에서 백엔드가 consent_check_node → waiting_agent 플로우를 처리함
        } else {
          // 일반 AI 응답 메시지 추가 (HANDOVER가 아닌 경우)
          console.log('[App] 녹음 모드 - 일반 AI 응답 (HANDOVER 아님), 메시지 표시 시작');
          console.log('[App] AI 응답 메시지 추가:', result.aiResponse.text);
          const aiMessageContent = result.aiResponse.text;
          const assistantMessage: Message = {
            id: `msg_${Date.now()}_assistant_${Math.random().toString(36).substring(2, 11)}`,
            role: 'assistant',
            content: aiMessageContent,
            timestamp: new Date(),
          };

          // 중복 메시지 방지: 최근 5개 메시지 중 동일 content가 있으면 추가하지 않음
          setMessages((prev) => {
            const recentMessages = prev.slice(-5);
            const isDuplicate = recentMessages.some(
              (m) => m.role === 'assistant' && m.content === aiMessageContent
            );
            if (isDuplicate) {
              console.log('[App] 중복 AI 메시지 무시:', aiMessageContent.substring(0, 30) + '...');
              return prev;
            }
            return [...prev, assistantMessage];
          });

          // 녹음 모드에서는 TTS 재생 (스트리밍 모드는 훅에서 자동 재생)
          if (isRecordingMode) {
            const recordResult = result as VoiceRecordingResult;
            if (recordResult.audioBase64) {
              playAudio(recordResult.audioBase64);
            }
          }
        }
      } else if (!isHandoverMode) {
        console.log('[App] aiResponse가 없거나 text가 비어있음');
      }
    } else {
      // result가 null인 경우 (빈 입력 등)
      emptyInputCountRef.current += 1;
      console.log(`[App] result가 null - 빈 입력 횟수: ${emptyInputCountRef.current}/${MAX_EMPTY_INPUTS}`);

      // 녹음 모드에서는 연속 녹음 안 함
      if (!isRecordingMode && isContinuousMode && !isHandoverMode && emptyInputCountRef.current < MAX_EMPTY_INPUTS) {
        // 연속 빈 입력이 아니면 다시 녹음 시작 (스트리밍 모드만)
        console.log('[App] 다시 녹음 시작...');
        setTimeout(() => {
          startRecording().catch((err: Error) => {
            console.error('[App] 재녹음 시작 실패:', err);
          });
        }, 500);
      } else if (emptyInputCountRef.current >= MAX_EMPTY_INPUTS) {
        // 연속 빈 입력 시 연속 대화 일시 중지
        console.log('[App] 연속 빈 입력 감지 - 연속 대화 일시 중지, 버튼 클릭 대기');
        emptyInputCountRef.current = 0;  // 카운터 초기화
      }
    }
  }, [stopRecording, isContinuousMode, isHandoverMode, startRecording, sessionId, isRecordingMode, playAudio]);

  // VAD 자동 중지 콜백 설정 (2초 침묵 시 자동 전송)
  // 백엔드에서 처리 완료 후 결과를 직접 받음 (EOS 전송 없이)
  // 중요: isHandoverModeRef.current를 사용하여 클로저 문제 해결
  useEffect(() => {
    setOnAutoStop(async (result) => {
      const currentHandoverMode = isHandoverModeRef.current;
      console.log('[App] VAD 자동 중지 결과:', result, 'isHandoverMode (ref):', currentHandoverMode);

      if (result) {
        // 사용자 메시지 추가
        if (result.userText?.trim()) {
          console.log('[App] 사용자 메시지 추가:', result.userText);
          emptyInputCountRef.current = 0;

          const userMessageContent = result.userText.trim();
          const userMessage: Message = {
            id: `msg_${Date.now()}_user_${Math.random().toString(36).substring(2, 11)}`,
            role: 'user',
            content: userMessageContent,
            timestamp: new Date(),
            isVoice: true,
          };

          // 중복 메시지 방지: 최근 5개 메시지 중 동일 content가 있으면 추가하지 않음
          setMessages((prev) => {
            const recentMessages = prev.slice(-5);
            const isDuplicate = recentMessages.some(
              (m) => m.role === 'user' && m.content === userMessageContent
            );
            if (isDuplicate) {
              console.log('[App] VAD - 중복 사용자 메시지 무시:', userMessageContent);
              return prev;
            }
            return [...prev, userMessage];
          });

          // 이관 모드일 때: AI 응답 무시하고 상담원에게 메시지 전송
          if (currentHandoverMode) {
            console.log('[App] 이관 모드 - 상담원에게 메시지 전송:', result.userText);
            try {
              await voiceApi.sendCustomerMessage(sessionId, result.userText.trim());
              console.log('[App] 상담원에게 메시지 전송 완료');
            } catch (err) {
              console.error('[App] 상담원에게 메시지 전송 실패:', err);
            }
            return; // AI 응답 처리 건너뛰기
          }
        } else {
          console.log('[App] userText가 비어있음');
        }

        // AI 응답 메시지 추가 (이관 모드가 아닐 때만)
        if (!currentHandoverMode && result.aiResponse?.text) {
          // HANDOVER 감지: suggestedAction 또는 메시지 내용으로 판단
          const isHandoverSuggested =
            result.aiResponse.suggestedAction === 'HANDOVER' ||
            result.aiResponse.suggestedAction === 'handover' ||
            result.aiResponse.text.includes('상담사에게 연결해 드리겠습니다') ||
            result.aiResponse.text.includes('상담원에게 연결');

          console.log('[App] AI 응답 처리 - suggestedAction:', result.aiResponse.suggestedAction, ', handoverStatus:', result.aiResponse.handoverStatus, ', isHandoverSuggested:', isHandoverSuggested);

          // handover_status가 pending이면 상담사 수락 대기 폴링 시작
          // 안내 메시지는 백엔드(waiting_agent)에서 이미 ai_message에 포함됨
          if (result.aiResponse.handoverStatus === 'pending') {
            console.log('[App] 음성 모드 - handover_status=pending 감지 - 상담사 수락 대기 폴링 시작');
            setIsWaitingForAgent(true);
            setHandoverTimeoutReached(false);
            startHandoverPollingRef.current?.();
          }

          // AI가 HANDOVER를 권장한 경우: AI 응답만 표시하고 고객 동의 대기
          if (isHandoverSuggested) {
            console.log('[App] AI가 HANDOVER 권장 - 고객 동의 대기');

            // AI 응답 메시지 표시 (고객에게 동의 요청)
            // 고객이 "네"라고 응답하면 백엔드의 consent_check_node가 처리함
            const assistantMessage: Message = {
              id: `msg_${Date.now()}_assistant`,
              role: 'assistant',
              content: result.aiResponse.text,
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMessage]);

            // TTS는 백엔드에서 이미 재생 중이므로 중단하지 않음
            // 고객이 "네"라고 응답할 때까지 대기
            // 다음 메시지에서 백엔드가 consent_check_node → waiting_agent 플로우를 처리함
          } else {
            // 일반 AI 응답 메시지 표시
            console.log('[App] AI 응답 메시지 추가:', result.aiResponse.text);
            const assistantMessage: Message = {
              id: `msg_${Date.now()}_assistant`,
              role: 'assistant',
              content: result.aiResponse.text,
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMessage]);
          }
        } else if (!currentHandoverMode) {
          console.log('[App] aiResponse가 없거나 text가 비어있음');
        }
      } else {
        // result가 null인 경우 (빈 입력 등)
        emptyInputCountRef.current += 1;
        console.log(`[App] result가 null - 빈 입력 횟수: ${emptyInputCountRef.current}/${MAX_EMPTY_INPUTS}`);

        const currentHandoverMode = isHandoverModeRef.current;
        if (isContinuousMode && !currentHandoverMode && emptyInputCountRef.current < MAX_EMPTY_INPUTS) {
          setTimeout(() => {
            startRecording().catch((err) => {
              console.error('[App] 재녹음 시작 실패:', err);
            });
          }, 500);
        } else if (emptyInputCountRef.current >= MAX_EMPTY_INPUTS) {
          console.log('[App] 연속 빈 입력 감지 - 연속 대화 일시 중지');
          emptyInputCountRef.current = 0;
        }
      }
    });
  }, [setOnAutoStop, isContinuousMode, startRecording, sessionId]);

  // TTS 재생 완료 콜백 설정 (연속 대화 모드일 때 자동 녹음 시작)
  // 중요: isHandoverModeRef.current를 사용하여 클로저 문제 해결
  useEffect(() => {
    setOnTTSComplete(() => {
      const currentHandoverMode = isHandoverModeRef.current;
      if (isContinuousMode && !currentHandoverMode) {
        console.log('[App] TTS 완료 - 자동 녹음 시작');
        startRecording().catch((err) => {
          console.error('[App] 자동 녹음 시작 실패:', err);
        });
      }
    });
  }, [setOnTTSComplete, isContinuousMode, startRecording]);

  // Barge-in 콜백 설정 (TTS 재생 중 사용자가 말하면 TTS 중단 + 녹음 시작)
  useEffect(() => {
    setOnBargeIn(() => {
      console.log('[App] Barge-in 감지 - 녹음 시작');
      startRecording().catch((err) => {
        console.error('[App] Barge-in 녹음 시작 실패:', err);
      });
    });
  }, [setOnBargeIn, startRecording]);

  // 마이크 버튼 클릭 핸들러
  const handleVoiceButtonClick = useCallback(async () => {
    console.log('[App] 버튼 클릭, isRecording:', isRecording);

    if (isRecording) {
      // 수동 녹음 중지
      await processStopRecording();
    } else {
      // 녹음 시작
      console.log('[App] 녹음 시작...');
      try {
        await startRecording();
        // 첫 녹음 시작 시 연속 대화 모드 활성화
        if (!isContinuousMode) {
          setIsContinuousMode(true);
          console.log('[App] 연속 대화 모드 활성화');
        }
        console.log('[App] 녹음 시작 완료');
      } catch (err) {
        console.error('녹음 시작 실패:', err);
      }
    }
  }, [isRecording, processStopRecording, startRecording, isContinuousMode]);

  // 새 상담 시작 (대화 초기화 + 인사 메시지 + TTS)
  const handleResetSession = useCallback(async () => {
    if (window.confirm('새로운 상담을 시작하시겠습니까?')) {
      // 상태 초기화
      setIsContinuousMode(false);
      setIsHandoverMode(false);
      setIsWaitingForAgent(false);
      setHandoverData(null);
      emptyInputCountRef.current = 0;
      lastMessageIdRef.current = 0;
      processedAgentMessageIdsRef.current.clear();
      handoverAcceptedProcessingRef.current = false;  // 핸드오버 처리 플래그 초기화

      // 세션 ID 리셋 및 새 세션 ID 생성
      resetSessionId();
      const newSessionId = getOrCreateSessionId();
      setSessionId(newSessionId);

      // 인사 메시지 표시
      const greetingMessage: Message = {
        id: `msg_${Date.now()}_greeting`,
        role: 'assistant',
        content: WELCOME_MESSAGE,
        timestamp: new Date(),
      };
      setMessages([greetingMessage]);

      // 인사 TTS 재생
      try {
        const ttsResponse = await voiceApi.requestTTS(WELCOME_MESSAGE);
        if (ttsResponse.audio_base64) {
          playAudio(ttsResponse.audio_base64);
        }
      } catch (err) {
        console.warn('인사 TTS 재생 실패:', err);
      }
    }
  }, [playAudio]);

  // 핸드오버 폴링 정리
  const cleanupHandoverPolling = useCallback(() => {
    if (handoverPollIntervalRef.current) {
      clearInterval(handoverPollIntervalRef.current);
      handoverPollIntervalRef.current = null;
    }
    if (handoverTimeoutRef.current) {
      clearTimeout(handoverTimeoutRef.current);
      handoverTimeoutRef.current = null;
    }
  }, []);

  // 상담사 수락 상태 폴링 시작
  const startHandoverPolling = useCallback(() => {
    // 기존 폴링 정리
    cleanupHandoverPolling();
    // accepted 처리 플래그 초기화 (새로운 폴링 시작)
    handoverAcceptedProcessingRef.current = false;

    // 상담사 수락 여부 폴링
    handoverPollIntervalRef.current = setInterval(async () => {
      // 이미 accepted 처리 중이면 스킵 (중복 방지)
      if (handoverAcceptedProcessingRef.current) {
        console.log('[App] 핸드오버 accepted 처리 중 - 스킵');
        return;
      }

      try {
        const status = await voiceApi.getHandoverStatus(sessionId);
        console.log('[App] 핸드오버 상태:', status.handover_status);

        if (status.handover_status === 'accepted') {
          // 중복 처리 방지 플래그 설정
          if (handoverAcceptedProcessingRef.current) {
            console.log('[App] 핸드오버 accepted 이미 처리됨 - 스킵');
            return;
          }
          handoverAcceptedProcessingRef.current = true;

          // 상담사가 수락함 → 모달 없이 바로 연결
          cleanupHandoverPolling();
          setIsWaitingForAgent(false);
          setIsHandoverMode(true);  // 상담사 메시지 폴링 시작

          // 연결 완료 안내 메시지
          const connectedMessage = '상담사에게 연결되었습니다. 상담을 시작합니다.';
          const aiMessage: Message = {
            id: `msg_${Date.now()}_agent_connected`,
            role: 'assistant',
            content: connectedMessage,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, aiMessage]);

          // TTS로 연결 완료 메시지 재생
          try {
            const ttsResponse = await voiceApi.requestTTS(connectedMessage);
            if (ttsResponse.audio_base64) {
              playAudio(ttsResponse.audio_base64);
            }
          } catch (ttsErr) {
            console.warn('TTS 재생 실패:', ttsErr);
          }
        } else if (status.handover_status === 'cancelled') {
          // 고객이 상담사 연결을 취소함
          console.log('[App] 핸드오버 취소됨 - 폴링 중지');
          cleanupHandoverPolling();
          setIsWaitingForAgent(false);
          // isHandoverMode는 false로 유지 (일반 대화로 복귀)
        }
      } catch (err) {
        console.error('[App] 핸드오버 상태 폴링 실패:', err);
      }
    }, HANDOVER_POLL_INTERVAL_MS);

    // 타임아웃 설정 - 메시지만 표시하고 폴링은 계속 유지
    handoverTimeoutRef.current = setTimeout(async () => {
      // 폴링은 계속 유지 (cleanupHandoverPolling 호출 안 함)
      // isWaitingForAgent도 true로 유지

      // 타임아웃 안내 메시지 (채팅창에 표시)
      const timeoutMessage: Message = {
        id: `msg_${Date.now()}_timeout`,
        role: 'assistant',
        content: HANDOVER_WAIT_TIME_MESSAGE + ' 계속 기다리시려면 잠시만 기다려 주세요. 추가 문의가 있으시면 말씀해 주세요.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, timeoutMessage]);

      // TTS 재생
      try {
        const ttsResponse = await voiceApi.requestTTS(timeoutMessage.content);
        if (ttsResponse.audio_base64) {
          playAudio(ttsResponse.audio_base64);
        }
      } catch (ttsErr) {
        console.warn('TTS 재생 실패:', ttsErr);
      }
    }, HANDOVER_TIMEOUT_MS);
  }, [sessionId, cleanupHandoverPolling, playAudio]);

  // startHandoverPolling ref 업데이트 (클로저 문제 해결)
  useEffect(() => {
    startHandoverPollingRef.current = startHandoverPolling;
  }, [startHandoverPolling]);

  // 상담원 연결 요청 (새로운 시나리오)
  const handleRequestHandover = useCallback(async () => {
    setIsHandoverLoading(true);
    try {
      // 1단계: 핸드오버 요청 → pending 상태로 설정
      const response = await voiceApi.requestHandoverWithStatus(sessionId);
      console.log('[App] 핸드오버 요청 응답:', response);

      // 안내 메시지 표시
      const waitingMessage: Message = {
        id: `msg_${Date.now()}_waiting`,
        role: 'assistant',
        content: '현재 응대 가능한 상담사가 있는지 확인을 해 보겠습니다. 잠시만 기다려 주시기 바랍니다.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, waitingMessage]);

      // TTS 재생
      try {
        const ttsResponse = await voiceApi.requestTTS(waitingMessage.content);
        if (ttsResponse.audio_base64) {
          playAudio(ttsResponse.audio_base64);
        }
      } catch (ttsErr) {
        console.warn('TTS 재생 실패:', ttsErr);
      }

      // 상담사 수락 대기 시작
      setIsWaitingForAgent(true);
      setHandoverTimeoutReached(false);
      startHandoverPolling();

    } catch (err) {
      console.error('상담원 이관 요청 실패:', err);
      alert('상담원 이관 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsHandoverLoading(false);
    }
  }, [sessionId, playAudio, startHandoverPolling]);
  void handleRequestHandover; // Reserved for future use

  // 고객이 상담사 연결 확인 (미사용 - 모달 제거로 자동 연결됨)
  const _handleConfirmAgentConnection = useCallback(async () => {
    // 중복 호출 방지
    if (isConfirmingHandoverRef.current) {
      console.log('[App] confirmHandover 이미 진행 중 - 스킵 (버튼)');
      return;
    }
    isConfirmingHandoverRef.current = true;
    setIsHandoverLoading(true);

    try {
      // 기존 handover/request 호출하여 분석 결과 가져오기
      const response = await voiceApi.confirmHandover(sessionId);
      setHandoverData(response);
      setIsHandoverMode(true);  // 실제 상담원 모드 활성화 → 메시지 폴링 시작

      // 연결 완료 메시지
      const connectedMessage: Message = {
        id: `msg_${Date.now()}_connected`,
        role: 'assistant',
        content: '상담원에게 연결되었습니다. 상담을 시작합니다.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, connectedMessage]);

      // TTS 재생
      try {
        const ttsResponse = await voiceApi.requestTTS(connectedMessage.content);
        if (ttsResponse.audio_base64) {
          playAudio(ttsResponse.audio_base64);
        }
      } catch (ttsErr) {
        console.warn('TTS 재생 실패:', ttsErr);
      }
    } catch (err) {
      console.error('상담원 연결 확인 실패:', err);
      alert('상담원 연결 중 오류가 발생했습니다.');
    } finally {
      setIsHandoverLoading(false);
      isConfirmingHandoverRef.current = false;
    }
  }, [sessionId, playAudio]);
  void _handleConfirmAgentConnection;

  // 고객이 상담사 연결 거부 (미사용 - 모달 제거됨)
  const _handleDeclineAgentConnection = useCallback(async () => {
    setIsWaitingForAgent(false);
    setHandoverTimeoutReached(false);
    setIsHandoverMode(false);  // 상담사 메시지 폴링 중지
    cleanupHandoverPolling();

    // 안내 메시지
    const declineMessage: Message = {
      id: `msg_${Date.now()}_decline`,
      role: 'assistant',
      content: '알겠습니다. 추가로 문의하실 내용이 있으시면 말씀해 주세요.',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, declineMessage]);

    // TTS 재생
    try {
      const ttsResponse = await voiceApi.requestTTS(declineMessage.content);
      if (ttsResponse.audio_base64) {
        playAudio(ttsResponse.audio_base64);
      }
    } catch (ttsErr) {
      console.warn('TTS 재생 실패:', ttsErr);
    }
  }, [cleanupHandoverPolling, playAudio]);
  void _handleDeclineAgentConnection;

  // 타임아웃 후 계속 대기 선택 (향후 확장용)
  const _handleContinueWaiting = useCallback(() => {
    setHandoverTimeoutReached(false);
    startHandoverPolling();  // 폴링 재시작

    const waitMessage: Message = {
      id: `msg_${Date.now()}_continue_wait`,
      role: 'assistant',
      content: '네, 계속 대기하겠습니다. 상담사가 응대 가능해지면 안내해 드리겠습니다.',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, waitMessage]);
  }, [startHandoverPolling]);
  void _handleContinueWaiting;

  // 컴포넌트 언마운트 시 핸드오버 폴링 정리
  useEffect(() => {
    return () => {
      cleanupHandoverPolling();
    };
  }, [cleanupHandoverPolling]);

  // 모달 닫기 (미사용 - 향후 확장용)
  const _handleCloseModal = useCallback(() => {
    setHandoverData(null);
  }, []);
  void _handleCloseModal;

  // 텍스트 메시지 전송
  const handleTextSubmit = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();

    const trimmedInput = textInput.trim();
    if (!trimmedInput || isTextSending) return;

    setIsTextSending(true);
    setTextInput('');

    // 사용자 메시지 추가
    const userMessage: Message = {
      id: `msg_${Date.now()}_user`,
      role: 'user',
      content: trimmedInput,
      timestamp: new Date(),
      isVoice: false,
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      // 이관 모드일 때: 상담원에게 메시지 전송
      if (isHandoverMode) {
        await voiceApi.sendCustomerMessage(sessionId, trimmedInput);
        console.log('[App] 상담원에게 텍스트 메시지 전송 완료');
      } else {
        // 일반 모드: AI 응답 받기
        const response = await voiceApi.sendTextMessage(sessionId, trimmedInput);

        console.log('[App] AI 응답:', {
          suggested_action: response.suggested_action,
          handover_status: response.handover_status,
          info_collection_complete: response.info_collection_complete
        });

        // AI 응답 메시지 추가
        const assistantMessage: Message = {
          id: `msg_${Date.now()}_assistant`,
          role: 'assistant',
          content: response.ai_message,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);

        // TTS 재생
        try {
          const ttsResponse = await voiceApi.requestTTS(response.ai_message);
          if (ttsResponse.audio_base64) {
            playAudio(ttsResponse.audio_base64);
          }
        } catch (ttsErr) {
          console.warn('TTS 재생 실패:', ttsErr);
        }

        // handover_status가 pending이면 상담사 수락 대기 폴링 시작
        // 안내 메시지는 백엔드(waiting_agent)에서 이미 ai_message에 포함되어 있으므로 추가 표시 불필요
        if (response.handover_status === 'pending' && !isWaitingForAgent) {
          console.log('[App] handover_status=pending 감지 - 상담사 수락 대기 폴링 시작');
          setIsWaitingForAgent(true);
          setHandoverTimeoutReached(false);
          startHandoverPolling();
        }
      }
    } catch (err) {
      console.error('텍스트 메시지 전송 실패:', err);
      // 에러 메시지 표시
      const errorMessage: Message = {
        id: `msg_${Date.now()}_error`,
        role: 'assistant',
        content: '죄송합니다. 메시지 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTextSending(false);
      textInputRef.current?.focus();
    }
  }, [textInput, isTextSending, isHandoverMode, sessionId, isWaitingForAgent, startHandoverPolling, playAudio]);

  // Enter 키 핸들러
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTextSubmit();
    }
  }, [handleTextSubmit]);

  const hasMessages = messages.length > 0;

  return (
    <div className="app">
      <div className="chat-window">
        {/* 헤더 */}
        <div className="chat-header">
          <div className="chat-header-content">
            <h1>미래카드 AICC 상담 보이스봇</h1>
            <p>음성 AI 기반 고객 상담 서비스</p>
          </div>
          <div className="header-actions">
            {/* 음성 모드 토글 */}
            <div className="voice-mode-toggle">
              <label className="toggle-label">
                <span className={!isRecordingMode ? 'active' : ''}>실시간</span>
                <input
                  type="checkbox"
                  checked={isRecordingMode}
                  onChange={(e) => setIsRecordingMode(e.target.checked)}
                  disabled={isRecording || isProcessing}
                />
                <span className="toggle-slider"></span>
                <span className={isRecordingMode ? 'active' : ''}>녹음</span>
              </label>
            </div>
            {/* 세션 정보 및 새 상담 버튼 */}
            <div className="session-info-header">
              <span className="session-id">세션: {formatSessionIdForDisplay(sessionId)}</span>
              <button onClick={handleResetSession} className="reset-button-header">
                새 상담
              </button>
            </div>
          </div>
        </div>

        {/* 메시지 영역 */}
        <div className="chat-messages">
          {/* 로딩 중 표시 (인사 메시지 대기) */}
          {!hasMessages && !hasGreeted && (
            <div className="loading-welcome">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <p>연결 중...</p>
            </div>
          )}

          {/* 메시지 목록 */}
          {hasMessages && (
            <>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}

              {/* 실시간 STT 표시 */}
              {isRecording && currentTranscript && (
                <div className="realtime-transcript">
                  <div className="transcript-content">
                    <span className="transcript-icon">🎤</span>
                    <span className="transcript-text">
                      {currentTranscript}
                      <span className="cursor-blink">|</span>
                    </span>
                  </div>
                </div>
              )}

              {/* 녹음 중 표시 (텍스트 없을 때) */}
              {isRecording && !currentTranscript && (
                <div className="recording-indicator">
                  <div className="recording-animation">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  <p>
                    {isRecordingMode
                      ? `녹음 중... ${recordingTime}초 (버튼을 눌러 전송)`
                      : '듣고 있습니다...'}
                  </p>
                </div>
              )}

              {isProcessing && (
                <div className="processing-message">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              )}

              {/* TTS 재생 중 표시 */}
              {isPlayingTTS && !isRecording && (
                <div className="tts-playing-indicator">
                  <span className="speaker-icon">🔊</span>
                  <span>응답 재생 중... (말씀하시면 중단됩니다)</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* 하단 입력 영역 */}
        <div className="chat-input-area">
          {/* 텍스트 입력 */}
          <form className="text-input-form" onSubmit={handleTextSubmit}>
            <input
              ref={textInputRef}
              type="text"
              className="text-input"
              placeholder={isHandoverMode ? "상담원에게 메시지 입력..." : "메시지를 입력하세요..."}
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isTextSending || isRecording || isProcessing}
            />
            <button
              type="submit"
              className="send-button"
              disabled={!textInput.trim() || isTextSending || isRecording || isProcessing}
            >
              {isTextSending ? '전송중...' : '전송'}
            </button>
          </form>

          {/* 음성 버튼 */}
          <VoiceButton
            isRecording={isRecording}
            isProcessing={isProcessing}
            onClick={handleVoiceButtonClick}
            size="small"
          />
        </div>
      </div>

      {/* 숨겨진 오디오 플레이어 */}
      <audio ref={audioRef} style={{ display: 'none' }} />

      {/* 모달들이 제거됨 - 상담사 수락 시 자동 연결 */}

      {/* 상담사 대기 중 표시 */}
      {isWaitingForAgent && (
        <div className="waiting-indicator">
          <div className="waiting-spinner"></div>
          <span>상담사 연결 대기 중...</span>
        </div>
      )}
    </div>
  );
}

export default App;
