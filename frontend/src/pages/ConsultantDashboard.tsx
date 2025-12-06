import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { HandoverResponse } from '../types/api';
import './ConsultantDashboard.css';

interface HandoverReportWithTimestamp extends HandoverResponse {
  session_id: string;
  timestamp: Date;
  processing_status: 'pending' | 'in_progress' | 'completed';
}

const ConsultantDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [reports, setReports] = useState<HandoverReportWithTimestamp[]>([]);
  const [selectedReport, setSelectedReport] = useState<HandoverReportWithTimestamp | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    // WebSocket 연결 (모든 세션의 handover_report 수신)
    const connectWebSocket = () => {
      const wsUrl = `ws://localhost:8000/api/v1/chat/ws/consultant_dashboard`;
      console.log('상담원 대시보드 WebSocket 연결 시도:', wsUrl);
      
      const websocket = new WebSocket(wsUrl);
      
      websocket.onopen = () => {
        console.log('✅ 상담원 대시보드 WebSocket 연결 성공');
      };
      
      websocket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('📩 상담원 대시보드 메시지 수신:', message);
          
          if (message.type === 'handover_report') {
            console.log('✅ handover_report 타입 확인됨');
            console.log('📦 데이터:', message.data);
            console.log('🔑 세션 ID:', message.session_id);
            
            // 데이터 구조 검증
            if (!message.data) {
              console.error('❌ message.data가 없습니다!');
              return;
            }
            
            // 🔍 상세 필드 로깅
            console.log('━━━ 수신 데이터 상세 ━━━');
            console.log('  status:', message.data.status);
            console.log('  customer_sentiment:', message.data.customer_sentiment);
            console.log('  summary:', message.data.summary);
            console.log('  summary 길이:', message.data.summary?.length, '자');
            console.log('  extracted_keywords:', message.data.extracted_keywords);
            console.log('  kms_recommendations:', message.data.kms_recommendations?.length, '개');
            console.log('━━━━━━━━━━━━━━━━━━━━━');
            
            const newReport: HandoverReportWithTimestamp = {
              status: message.data.status || 'success',
              analysis_result: {
                customer_sentiment: message.data.customer_sentiment || 'NEUTRAL',
                summary: message.data.summary || '요약 정보 없음',
                extracted_keywords: message.data.extracted_keywords || [],
                kms_recommendations: message.data.kms_recommendations || []
              },
              session_id: message.session_id || `sess_${Date.now()}`,
              timestamp: new Date(),
              processing_status: 'pending'
            };
            
            console.log('📝 생성된 리포트:');
            console.log('  session_id:', newReport.session_id);
            console.log('  summary:', newReport.analysis_result.summary);
            console.log('  keywords:', newReport.analysis_result.extracted_keywords);
            
            setReports(prev => {
              const updated = [newReport, ...prev];
              console.log('📊 업데이트된 리포트 목록:', updated.length, '개');
              return updated;
            });
            
            // 알림음 재생 (선택사항)
            playNotificationSound();
          } else if (message.type === 'status') {
            console.log('ℹ️ 상태 메시지:', message.message);
          } else {
            console.log('⚠️ 알 수 없는 메시지 타입:', message.type);
          }
        } catch (error) {
          console.error('❌ 메시지 파싱 오류:', error);
          console.error('원본 데이터:', event.data);
        }
      };
      
      websocket.onerror = (error) => {
        console.error('WebSocket 오류:', error);
      };
      
      websocket.onclose = () => {
        console.log('WebSocket 연결 종료, 5초 후 재연결 시도...');
        setTimeout(connectWebSocket, 5000);
      };
      
      setWs(websocket);
    };
    
    connectWebSocket();
    
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, []);

  const playNotificationSound = () => {
    // 브라우저 알림음 (선택사항)
    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZUQ8PUKjl8q5hGATChM/u2Yk9BxFrv/DjnU4JClCo5fKuYRgEwoTP7tmJPQcRa7/w451OCQpQqOXyrmEYBMKEz+7ZiT0HEWu/8OOdTgkKUKjl8q5hGATChM/u2Yk9BxFrv/DjnU4JClCo5fKuYRgEwoTP7tmJPQcRa7/w451OCQpQqOXyrmEYBMKEz+7ZiT0HEWu/8OOdTgkKUKjl8q5hGATChM/u2Yk9BxFrv/DjnU4JClCo5fKuYRgEwoTP7tmJPQcRa7/w451OCQpQqOXyrmEYBMKEz+7ZiT0HEWu/8OOdTgkKUKjl8q5hGATChM/u2Yk9BxFrv/DjnU4JClCo5fKuYRgEwoTP7tmJPQcRa7/w451OCQpQqOXyrmEYBMKEz+7ZiT0HEWu/8OOdTgkKUKjl8q5hGATChM/u2Yk9BxFrv/DjnU4JClCo5fKuYRgEwoTP7tmJPQcRa7/w451OCQpQqOXyrmEYBMKEz+7ZiT0HEWu/8OOdTgkKUKjl8q5hGATChM/u2Yk9BxFrv/DjnU4JClCo5fKuYRgE');
    audio.play().catch(() => {
      // 자동 재생 차단 시 무시
    });
  };

  const handleStatusChange = (sessionId: string, newStatus: 'pending' | 'in_progress' | 'completed') => {
    setReports(prev =>
      prev.map(report =>
        report.session_id === sessionId
          ? { ...report, processing_status: newStatus }
          : report
      )
    );
  };

  const getSentimentEmoji = (sentiment: string) => {
    switch (sentiment) {
      case 'POSITIVE': return '😊';
      case 'NEUTRAL': return '😐';
      case 'NEGATIVE': return '😟';
      case 'URGENT': return '🚨';
      default: return '❓';
    }
  };

  const getSentimentText = (sentiment: string) => {
    switch (sentiment) {
      case 'POSITIVE': return '긍정적';
      case 'NEUTRAL': return '중립적';
      case 'NEGATIVE': return '부정적';
      case 'URGENT': return '긴급';
      default: return '알 수 없음';
    }
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { color: string; text: string }> = {
      pending: { color: '#ff9800', text: '대기 중' },
      in_progress: { color: '#2196f3', text: '처리 중' },
      completed: { color: '#4caf50', text: '완료' }
    };
    return badges[status] || { color: '#9e9e9e', text: '알 수 없음' };
  };

  return (
    <div className="consultant-dashboard">
      <header className="dashboard-header">
        <div className="header-left">
          <h1>🎧 상담원 대시보드</h1>
          <button
            className="btn-back"
            onClick={() => navigate('/')}
          >
            💬 채팅으로 돌아가기
          </button>
        </div>
        <div className="header-stats">
          <div className="stat-item">
            <span className="stat-label">전체</span>
            <span className="stat-value">{reports.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">대기</span>
            <span className="stat-value">{reports.filter(r => r.processing_status === 'pending').length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">진행</span>
            <span className="stat-value">{reports.filter(r => r.processing_status === 'in_progress').length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">완료</span>
            <span className="stat-value">{reports.filter(r => r.processing_status === 'completed').length}</span>
          </div>
        </div>
      </header>

      <div className="dashboard-content">
        <aside className="reports-sidebar">
          <h2>이관 요청 목록</h2>
          {reports.length === 0 ? (
            <div className="no-reports">
              <p>📭 아직 이관 요청이 없습니다</p>
            </div>
          ) : (
            <div className="reports-list">
              {reports.map(report => {
                const badge = getStatusBadge(report.processing_status);
                return (
                  <div
                    key={report.session_id}
                    className={`report-card ${selectedReport?.session_id === report.session_id ? 'active' : ''}`}
                    onClick={() => setSelectedReport(report)}
                  >
                    <div className="report-card-header">
                      <span className="session-id">세션 {report.session_id.slice(-8)}</span>
                      <span
                        className="status-badge"
                        style={{ backgroundColor: badge.color }}
                      >
                        {badge.text}
                      </span>
                    </div>
                    <div className="report-card-body">
                      <div className="sentiment-indicator">
                        <span className="sentiment-emoji">
                          {getSentimentEmoji(report.analysis_result.customer_sentiment)}
                        </span>
                        <span className="sentiment-text">
                          {getSentimentText(report.analysis_result.customer_sentiment)}
                        </span>
                      </div>
                      <div className="report-time">
                        {report.timestamp.toLocaleTimeString('ko-KR')}
                      </div>
                    </div>
                    {report.processing_status === 'pending' && (
                      <div className="report-card-actions">
                        <button
                          className="btn-start"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStatusChange(report.session_id, 'in_progress');
                            setSelectedReport(report);
                          }}
                        >
                          시작하기
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </aside>

        <main className="report-details">
          {selectedReport ? (
            <>
              <div className="details-header">
                <h2>상담 이관 상세 정보</h2>
                <div className="details-actions">
                  {selectedReport.processing_status === 'in_progress' && (
                    <button
                      className="btn-complete"
                      onClick={() => handleStatusChange(selectedReport.session_id, 'completed')}
                    >
                      ✓ 완료 처리
                    </button>
                  )}
                  {selectedReport.processing_status === 'pending' && (
                    <button
                      className="btn-start-large"
                      onClick={() => handleStatusChange(selectedReport.session_id, 'in_progress')}
                    >
                      ▶ 상담 시작
                    </button>
                  )}
                </div>
              </div>

              <div className="details-content">
                <section className="detail-section">
                  <h3>📊 고객 감정 상태</h3>
                  <div className="sentiment-display">
                    <span className="sentiment-emoji-large">
                      {getSentimentEmoji(selectedReport.analysis_result.customer_sentiment)}
                    </span>
                    <span className="sentiment-text-large">
                      {getSentimentText(selectedReport.analysis_result.customer_sentiment)}
                    </span>
                  </div>
                </section>

                <section className="detail-section">
                  <h3>📝 대화 요약</h3>
                  <div className="summary-text">
                    {selectedReport.analysis_result.summary}
                  </div>
                </section>

                <section className="detail-section">
                  <h3>🔑 핵심 키워드</h3>
                  <div className="keywords-list">
                    {selectedReport.analysis_result.extracted_keywords.map((keyword, index) => (
                      <span key={index} className="keyword-tag">
                        {keyword}
                      </span>
                    ))}
                  </div>
                </section>

                {selectedReport.analysis_result.kms_recommendations.length > 0 && (
                  <section className="detail-section">
                    <h3>📚 추천 KMS 문서</h3>
                    <div className="kms-list">
                      {selectedReport.analysis_result.kms_recommendations.map((kms, index) => (
                        <div key={index} className="kms-item">
                          <div className="kms-header">
                            <span className="kms-title">{kms.title}</span>
                            <span className="kms-score">
                              {(kms.relevance_score * 100).toFixed(0)}%
                            </span>
                          </div>
                          <a
                            href={kms.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="kms-link"
                          >
                            문서 열기 →
                          </a>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                <section className="detail-section">
                  <h3>ℹ️ 세션 정보</h3>
                  <div className="session-info">
                    <div className="info-row">
                      <span className="info-label">세션 ID:</span>
                      <span className="info-value">{selectedReport.session_id}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">접수 시간:</span>
                      <span className="info-value">
                        {selectedReport.timestamp.toLocaleString('ko-KR')}
                      </span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">상태:</span>
                      <span className="info-value">
                        <span
                          className="status-badge-inline"
                          style={{ backgroundColor: getStatusBadge(selectedReport.processing_status).color }}
                        >
                          {getStatusBadge(selectedReport.processing_status).text}
                        </span>
                      </span>
                    </div>
                  </div>
                </section>
              </div>
            </>
          ) : (
            <div className="no-selection">
              <p>왼쪽 목록에서 이관 요청을 선택하세요</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default ConsultantDashboard;

