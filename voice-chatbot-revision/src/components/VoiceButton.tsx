import React from 'react';
import './VoiceButton.css';

interface VoiceButtonProps {
  isRecording: boolean;
  isProcessing: boolean;
  onClick: () => void;
  size?: 'small' | 'large';
}

const VoiceButton: React.FC<VoiceButtonProps> = ({
  isRecording,
  isProcessing,
  onClick,
  size = 'large',
}) => {
  const getButtonClass = () => {
    let className = `voice-button voice-button--${size}`;
    if (isRecording) className += ' voice-button--recording';
    if (isProcessing) className += ' voice-button--processing';
    return className;
  };

  const getIcon = () => {
    if (isProcessing) {
      return (
        <div className="processing-spinner">
          <div className="spinner"></div>
        </div>
      );
    }

    return (
      <svg
        className="mic-icon"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
      </svg>
    );
  };

  return (
    <button
      className={getButtonClass()}
      onClick={onClick}
      disabled={isProcessing}
      aria-label={isRecording ? '녹음 중지' : '음성 입력 시작'}
    >
      {isRecording && <div className="pulse-ring"></div>}
      {getIcon()}
    </button>
  );
};

export default VoiceButton;
