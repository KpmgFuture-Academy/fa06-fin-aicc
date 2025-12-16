/**
 * 타이핑 효과 훅
 *
 * 텍스트를 한 글자씩 표시하는 타이핑 효과를 제공합니다.
 * - 새 메시지에만 적용 (isActive가 true일 때)
 * - 스킵 기능 지원 (클릭 시 전체 텍스트 즉시 표시)
 */

import { useState, useEffect, useCallback } from 'react';

interface UseTypingEffectOptions {
  speed?: number;           // 한 글자당 ms (기본: 30ms)
  onComplete?: () => void;  // 타이핑 완료 콜백
}

interface UseTypingEffectReturn {
  displayedText: string;    // 현재 표시되는 텍스트
  isTyping: boolean;        // 타이핑 중 여부
  skipTyping: () => void;   // 스킵 함수 (즉시 전체 표시)
}

export const useTypingEffect = (
  text: string,
  isActive: boolean,
  options: UseTypingEffectOptions = {}
): UseTypingEffectReturn => {
  const { speed = 30, onComplete } = options;

  // isActive가 false면 처음부터 전체 텍스트 표시
  const [displayedText, setDisplayedText] = useState(isActive ? '' : text);
  const [isTyping, setIsTyping] = useState(isActive);
  const [currentIndex, setCurrentIndex] = useState(isActive ? 0 : text.length);

  // 스킵 함수: 즉시 전체 텍스트 표시
  const skipTyping = useCallback(() => {
    setDisplayedText(text);
    setCurrentIndex(text.length);
    setIsTyping(false);
    onComplete?.();
  }, [text, onComplete]);

  // 텍스트가 변경되면 초기화
  useEffect(() => {
    if (isActive) {
      setDisplayedText('');
      setCurrentIndex(0);
      setIsTyping(true);
    } else {
      setDisplayedText(text);
      setCurrentIndex(text.length);
      setIsTyping(false);
    }
  }, [text, isActive]);

  // 타이핑 애니메이션
  useEffect(() => {
    if (!isTyping || currentIndex >= text.length) {
      if (currentIndex >= text.length && isTyping) {
        setIsTyping(false);
        onComplete?.();
      }
      return;
    }

    const timer = setTimeout(() => {
      setDisplayedText(text.slice(0, currentIndex + 1));
      setCurrentIndex((prev) => prev + 1);
    }, speed);

    return () => clearTimeout(timer);
  }, [currentIndex, isTyping, text, speed, onComplete]);

  return {
    displayedText,
    isTyping,
    skipTyping,
  };
};

export default useTypingEffect;
