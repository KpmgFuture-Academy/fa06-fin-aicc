import React, { useState, useCallback, useRef, useEffect } from 'react';
import VoiceButton from './components/VoiceButton';
import ChatMessage, { Message } from './components/ChatMessage';
import { useAudioRecorder } from './hooks/useAudioRecorder';
import { voiceApi, getOrCreateSessionId, resetSessionId, HandoverResponse } from './services/api';
import './App.css';

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [sessionId] = useState(() => getOrCreateSessionId());
  const [handoverData, setHandoverData] = useState<HandoverResponse | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const { isRecording, startRecording, stopRecording, error } = useAudioRecorder();

  // 메시지 추가 시 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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

  // 마이크 버튼 클릭 핸들러
  const handleVoiceButtonClick = useCallback(async () => {
    if (isRecording) {
      // 녹음 중지 및 전송
      const audioBlob = await stopRecording();

      if (!audioBlob) {
        console.error('녹음 데이터 없음');
        return;
      }

      setIsProcessing(true);

      try {
        const response = await voiceApi.sendVoiceMessage(sessionId, audioBlob);

        // 사용자 메시지 추가 (STT 결과)
        const userMessage: Message = {
          id: `msg_${Date.now()}_user`,
          role: 'user',
          content: response.transcribed_text,
          timestamp: new Date(),
          isVoice: true,
        };
        setMessages((prev) => [...prev, userMessage]);

        // AI 응답 메시지 추가
        const assistantMessage: Message = {
          id: `msg_${Date.now()}_assistant`,
          role: 'assistant',
          content: response.ai_message,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);

        // TTS 오디오 재생
        if (response.audio_base64) {
          playAudio(response.audio_base64);
        }
      } catch (err: any) {
        console.error('음성 처리 실패:', err);

        const errorMessage: Message = {
          id: `msg_${Date.now()}_error`,
          role: 'assistant',
          content: err?.response?.data?.detail || '음성 처리 중 오류가 발생했습니다. 다시 시도해주세요.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsProcessing(false);
      }
    } else {
      // 녹음 시작
      await startRecording();
    }
  }, [isRecording, stopRecording, startRecording, sessionId, playAudio]);

  // 새 상담 시작
  const handleResetSession = useCallback(() => {
    if (window.confirm('새로운 상담을 시작하시겠습니까?')) {
      resetSessionId();
      setMessages([]);
      window.location.reload();
    }
  }, []);

  // 상담원 연결 요청
  const handleRequestHandover = useCallback(async () => {
    setIsProcessing(true);
    try {
      const response = await voiceApi.requestHandover(sessionId);
      setHandoverData(response);
    } catch (err) {
      console.error('상담원 이관 요청 실패:', err);
      alert('상담원 이관 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsProcessing(false);
    }
  }, [sessionId]);

  // 모달 닫기
  const handleCloseModal = useCallback(() => {
    setHandoverData(null);
  }, []);

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
          <button
            className="handover-button"
            onClick={handleRequestHandover}
            disabled={isProcessing}
          >
            상담원 연결
          </button>
        </div>

        {/* 메시지 영역 */}
        <div className="chat-messages">
          {!hasMessages ? (
            <div className="welcome-message">
              <VoiceButton
                isRecording={isRecording}
                isProcessing={isProcessing}
                onClick={handleVoiceButtonClick}
                size="large"
              />
              <h2>안녕하세요! 무엇을 도와드릴까요?</h2>
              <p>
                {isRecording
                  ? '말씀해주세요... (버튼을 다시 눌러 전송)'
                  : '마이크 버튼을 눌러 말씀해주세요'}
              </p>
              {error && <p className="error-message">{error}</p>}
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {isProcessing && (
                <div className="processing-message">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* 하단 입력 영역 - 메시지가 있을 때만 표시 */}
        {hasMessages && (
          <div className="chat-input-area">
            <VoiceButton
              isRecording={isRecording}
              isProcessing={isProcessing}
              onClick={handleVoiceButtonClick}
              size="small"
            />
            <span className="input-hint">
              {isRecording ? '녹음 중... 버튼을 눌러 전송' : '버튼을 눌러 음성 입력'}
            </span>
          </div>
        )}
      </div>

      {/* 세션 정보 */}
      <div className="session-info">
        <span>세션: {sessionId}</span>
        <button onClick={handleResetSession} className="reset-button">
          새 상담 시작
        </button>
      </div>

      {/* 숨겨진 오디오 플레이어 */}
      <audio ref={audioRef} style={{ display: 'none' }} />

      {/* 상담원 이관 모달 */}
      {handoverData && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>상담원 연결 요청 완료</h2>
            <p>{handoverData.message}</p>

            <div className="analysis-section">
              <h3>AI 분석 결과</h3>
              <div className="analysis-item">
                <span className="analysis-label">의도:</span>
                <span className="analysis-value">{handoverData.ai_analysis.intent}</span>
              </div>
              <div className="analysis-item">
                <span className="analysis-label">감정:</span>
                <span className="analysis-value">{handoverData.ai_analysis.sentiment}</span>
              </div>
              <div className="analysis-item">
                <span className="analysis-label">담당 부서:</span>
                <span className="analysis-value">{handoverData.ai_analysis.recommended_department}</span>
              </div>
              <div className="analysis-item">
                <span className="analysis-label">우선순위:</span>
                <span className="analysis-value">{handoverData.priority}</span>
              </div>
              {handoverData.ai_analysis.key_issues.length > 0 && (
                <div className="key-issues">
                  <span className="analysis-label">핵심 이슈:</span>
                  <ul>
                    {handoverData.ai_analysis.key_issues.map((issue, idx) => (
                      <li key={idx}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="analysis-item" style={{ marginTop: '12px' }}>
                <span className="analysis-label">요약:</span>
                <span className="analysis-value">{handoverData.ai_analysis.summary}</span>
              </div>
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
