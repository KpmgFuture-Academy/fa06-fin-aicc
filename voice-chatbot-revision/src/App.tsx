import { useState, useCallback, useRef, useEffect } from 'react';
import VoiceButton from './components/VoiceButton';
import ChatMessage, { Message } from './components/ChatMessage';
import { useVoiceStream } from './hooks/useVoiceStream';
import { voiceApi, getOrCreateSessionId, resetSessionId, formatSessionIdForDisplay, HandoverResponse } from './services/api';
import './App.css';

// 자동 인사 메시지 설정
const WELCOME_MESSAGE = "안녕하세요 고객님, 카드 상담 보이스봇에 연결되었습니다. 무엇을 도와 드릴까요? 음성 상담 및 텍스트 상담 모두 가능합니다.";
const WELCOME_DELAY_MS = 2000; // 2초 후 인사

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId] = useState(() => getOrCreateSessionId());
  const [handoverData, setHandoverData] = useState<HandoverResponse | null>(null);
  const [isHandoverMode, setIsHandoverMode] = useState(false);  // 상담원 연결 모드
  const [isHandoverLoading, setIsHandoverLoading] = useState(false);  // 상담원 연결 로딩 상태
  const [textInput, setTextInput] = useState('');  // 텍스트 입력 상태
  const [isTextSending, setIsTextSending] = useState(false);  // 텍스트 전송 중 상태
  const [hasGreeted, setHasGreeted] = useState(false);  // 인사 메시지 표시 여부
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textInputRef = useRef<HTMLInputElement>(null);
  const isHandoverModeRef = useRef(false);  // 클로저 문제 해결용 ref
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastMessageIdRef = useRef<number>(0);  // 마지막 메시지 ID (폴링용)
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 양방향 스트리밍 훅 사용 (STT + AI + TTS 통합)
  const {
    isRecording,
    isConnected,
    isProcessing,
    isPlayingTTS,
    transcript,
    finalTranscript,
    error: sttError,
    startRecording,
    stopRecording,
    setOnAutoStop,
    setOnTTSComplete,
    setOnBargeIn,
  } = useVoiceStream(sessionId);

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
  useEffect(() => {
    if (!isHandoverMode) return;

    const pollAgentMessages = async () => {
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
          // 상담원 메시지만 필터링 (role === 'assistant')
          const agentMessages = newMessages.filter((m: any) => m.role === 'assistant');

          for (const msg of agentMessages) {
            // 이미 표시된 메시지인지 확인
            if (msg.id <= lastMessageIdRef.current) continue;

            // 메시지 추가 (인간 상담사 메시지로 표시)
            const newMessage: Message = {
              id: `msg_agent_${msg.id}`,
              role: 'assistant',
              content: msg.message,
              timestamp: new Date(msg.created_at),
              isAgent: true,  // 인간 상담사 메시지
            };
            setMessages((prev) => [...prev, newMessage]);

            // TTS 재생
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

          // 마지막 메시지 ID 업데이트
          const maxId = Math.max(...newMessages.map((m: any) => m.id));
          lastMessageIdRef.current = maxId;
        }
      } catch (err) {
        console.error('상담원 메시지 폴링 실패:', err);
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
    console.log('[App] 녹음 중지 시작...', 'isHandoverMode:', isHandoverMode);
    const result = await stopRecording();
    console.log('[App] stopRecording 결과:', result);

    if (result) {
      // 사용자 메시지 추가 (서버에서 받은 final_text 사용)
      if (result.userText?.trim()) {
        console.log('[App] 사용자 메시지 추가:', result.userText);
        // 성공적인 입력 시 빈 입력 카운터 초기화
        emptyInputCountRef.current = 0;

        const userMessage: Message = {
          id: `msg_${Date.now()}_user`,
          role: 'user',
          content: result.userText.trim(),
          timestamp: new Date(),
          isVoice: true,
        };
        setMessages((prev) => [...prev, userMessage]);

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

      // AI 응답 메시지 추가 (이관 모드가 아닐 때만, 훅에서 자동으로 TTS 재생됨)
      if (!isHandoverMode && result.aiResponse?.text) {
        console.log('[App] AI 응답 메시지 추가:', result.aiResponse.text);
        const assistantMessage: Message = {
          id: `msg_${Date.now()}_assistant`,
          role: 'assistant',
          content: result.aiResponse.text,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } else if (!isHandoverMode) {
        console.log('[App] aiResponse가 없거나 text가 비어있음');
      }
    } else {
      // result가 null인 경우 (빈 입력 등)
      emptyInputCountRef.current += 1;
      console.log(`[App] result가 null - 빈 입력 횟수: ${emptyInputCountRef.current}/${MAX_EMPTY_INPUTS}`);

      if (isContinuousMode && !isHandoverMode && emptyInputCountRef.current < MAX_EMPTY_INPUTS) {
        // 연속 빈 입력이 아니면 다시 녹음 시작
        console.log('[App] 다시 녹음 시작...');
        setTimeout(() => {
          startRecording().catch((err) => {
            console.error('[App] 재녹음 시작 실패:', err);
          });
        }, 500);
      } else if (emptyInputCountRef.current >= MAX_EMPTY_INPUTS) {
        // 연속 빈 입력 시 연속 대화 일시 중지
        console.log('[App] 연속 빈 입력 감지 - 연속 대화 일시 중지, 버튼 클릭 대기');
        emptyInputCountRef.current = 0;  // 카운터 초기화
      }
    }
  }, [stopRecording, isContinuousMode, isHandoverMode, startRecording, sessionId]);

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

          const userMessage: Message = {
            id: `msg_${Date.now()}_user`,
            role: 'user',
            content: result.userText.trim(),
            timestamp: new Date(),
            isVoice: true,
          };
          setMessages((prev) => [...prev, userMessage]);

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
          console.log('[App] AI 응답 메시지 추가:', result.aiResponse.text);
          const assistantMessage: Message = {
            id: `msg_${Date.now()}_assistant`,
            role: 'assistant',
            content: result.aiResponse.text,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, assistantMessage]);
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

  // 새 상담 시작
  const handleResetSession = useCallback(() => {
    if (window.confirm('새로운 상담을 시작하시겠습니까?')) {
      setIsContinuousMode(false);
      resetSessionId();
      setMessages([]);
      window.location.reload();
    }
  }, []);

  // 상담원 연결 요청
  const handleRequestHandover = useCallback(async () => {
    setIsHandoverLoading(true);
    try {
      const response = await voiceApi.requestHandover(sessionId);
      setHandoverData(response);
      setIsHandoverMode(true);  // 상담원 모드 활성화 → 폴링 시작

      // 상담원 연결 메시지 추가
      const systemMessage: Message = {
        id: `msg_${Date.now()}_system`,
        role: 'assistant',
        content: '상담원에게 연결되었습니다. 잠시만 기다려주세요.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, systemMessage]);

    } catch (err) {
      console.error('상담원 이관 요청 실패:', err);
      alert('상담원 이관 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsHandoverLoading(false);
    }
  }, [sessionId]);

  // 모달 닫기
  const handleCloseModal = useCallback(() => {
    setHandoverData(null);
  }, []);

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
            const audioBlob = base64ToBlob(ttsResponse.audio_base64, 'audio/mp3');
            const audioUrl = URL.createObjectURL(audioBlob);
            if (audioRef.current) {
              audioRef.current.src = audioUrl;
              audioRef.current.play();
            }
          }
        } catch (ttsErr) {
          console.warn('TTS 재생 실패:', ttsErr);
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
  }, [textInput, isTextSending, isHandoverMode, sessionId]);

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
            <h1>Bank AICC 상담 보이스봇</h1>
            <p>음성 AI 기반 고객 상담 서비스</p>
          </div>
          <div className="header-actions">
            <div className="session-info-header">
              <span className="session-id">세션: {formatSessionIdForDisplay(sessionId)}</span>
              <button onClick={handleResetSession} className="reset-button-header">
                새 상담
              </button>
            </div>
            <button
              className="handover-button"
              onClick={handleRequestHandover}
              disabled={isHandoverLoading || isProcessing}
            >
              상담원 연결
            </button>
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
                  <p>듣고 있습니다...</p>
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

      {/* 상담원 이관 모달 */}
      {handoverData && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>상담원 연결 요청 완료</h2>
            <p>상담 내용이 분석되었습니다.</p>

            <div className="analysis-section">
              <h3>AI 분석 결과</h3>
              <div className="analysis-item">
                <span className="analysis-label">고객 감정:</span>
                <span className="analysis-value">{handoverData.analysis_result.customer_sentiment}</span>
              </div>
              <div className="analysis-item" style={{ marginTop: '12px' }}>
                <span className="analysis-label">요약:</span>
                <span className="analysis-value">{handoverData.analysis_result.summary}</span>
              </div>
              {handoverData.analysis_result.extracted_keywords.length > 0 && (
                <div className="key-issues">
                  <span className="analysis-label">핵심 키워드:</span>
                  <ul>
                    {handoverData.analysis_result.extracted_keywords.map((keyword, idx) => (
                      <li key={idx}>{keyword}</li>
                    ))}
                  </ul>
                </div>
              )}
              {handoverData.analysis_result.kms_recommendations.length > 0 && (
                <div className="key-issues" style={{ marginTop: '12px' }}>
                  <span className="analysis-label">추천 문서:</span>
                  <ul>
                    {handoverData.analysis_result.kms_recommendations.map((rec, idx) => (
                      <li key={idx}>
                        <a href={rec.url} target="_blank" rel="noopener noreferrer">
                          {rec.title}
                        </a>
                        <span style={{ fontSize: '0.8em', color: '#888' }}> (관련도: {(rec.relevance_score * 100).toFixed(0)}%)</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <button className="modal-close-button" onClick={handleCloseModal}>
              확인
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
