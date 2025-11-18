import React from 'react';
import type { HandoverResponse } from '../types/api';
import './HandoverModal.css';

interface HandoverModalProps {
  data: HandoverResponse | null;
  onClose: () => void;
}

const HandoverModal: React.FC<HandoverModalProps> = ({ data, onClose }) => {
  if (!data) return null;

  const { analysis_result } = data;

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'POSITIVE':
        return '#4caf50';
      case 'NEGATIVE':
        return '#f44336';
      default:
        return '#ff9800';
    }
  };

  const getSentimentText = (sentiment: string) => {
    switch (sentiment) {
      case 'POSITIVE':
        return '긍정적';
      case 'NEGATIVE':
        return '부정적';
      default:
        return '중립적';
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>상담원 이관 분석 결과</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="analysis-section">
            <h3>고객 감정 상태</h3>
            <div
              className="sentiment-badge"
              style={{ backgroundColor: getSentimentColor(analysis_result.customer_sentiment) }}
            >
              {getSentimentText(analysis_result.customer_sentiment)}
            </div>
          </div>

          <div className="analysis-section">
            <h3>상담 요약</h3>
            <div className="summary-text">
              {analysis_result.summary.split('\n').map((line, idx) => (
                <p key={idx}>{line}</p>
              ))}
            </div>
          </div>

          {analysis_result.extracted_keywords.length > 0 && (
            <div className="analysis-section">
              <h3>핵심 키워드</h3>
              <div className="keywords-list">
                {analysis_result.extracted_keywords.map((keyword, idx) => (
                  <span key={idx} className="keyword-tag">
                    {keyword}
                  </span>
                ))}
              </div>
            </div>
          )}

          {analysis_result.kms_recommendations.length > 0 && (
            <div className="analysis-section">
              <h3>추천 문서</h3>
              <div className="kms-recommendations">
                {analysis_result.kms_recommendations.map((rec, idx) => (
                  <a
                    key={idx}
                    href={rec.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="kms-item"
                  >
                    <div className="kms-title">{rec.title}</div>
                    <div className="kms-meta">
                      관련도: {(rec.relevance_score * 100).toFixed(1)}%
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="confirm-button" onClick={onClose}>
            확인
          </button>
        </div>
      </div>
    </div>
  );
};

export default HandoverModal;

