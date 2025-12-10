/**
 * 음성 녹음 훅 (디버깅용 녹음 모드)
 *
 * 실시간 스트리밍 대신 녹음 후 REST API로 전송하는 방식
 * - 버튼 클릭으로 녹음 시작/중지
 * - 녹음 완료 후 /api/v1/voice/message로 전송
 * - STT → AI → TTS 응답 수신
 */

import { useState, useRef, useCallback } from 'react';
import { voiceApi } from '../services/api';

export interface VoiceRecordingResult {
  userText: string;
  aiResponse: {
    text: string;
    intent: string;
    suggestedAction: string;
    handoverStatus?: string | null;  // 핸드오버 상태 (pending, accepted, declined, timeout)
  } | null;
  audioBase64: string | null;
}

interface UseVoiceRecordingReturn {
  isRecording: boolean;
  isProcessing: boolean;
  error: string | null;
  recordingTime: number;  // 녹음 시간 (초)
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<VoiceRecordingResult | null>;
}

export const useVoiceRecording = (sessionId: string): UseVoiceRecordingReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 녹음 시작
  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setRecordingTime(0);
      audioChunksRef.current = [];

      // 마이크 접근
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // MediaRecorder 설정
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start(100); // 100ms마다 데이터 수집
      setIsRecording(true);

      // 녹음 시간 타이머
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);

      console.log('[VoiceRecording] 녹음 시작');
    } catch (err) {
      console.error('[VoiceRecording] 녹음 시작 실패:', err);
      setError('마이크 접근 권한이 필요합니다.');
      throw err;
    }
  }, []);

  // 녹음 중지 및 전송
  const stopRecording = useCallback(async (): Promise<VoiceRecordingResult | null> => {
    return new Promise((resolve) => {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
        console.log('[VoiceRecording] 녹음이 활성화되지 않음');
        resolve(null);
        return;
      }

      // 타이머 중지
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      const mediaRecorder = mediaRecorderRef.current;

      mediaRecorder.onstop = async () => {
        setIsRecording(false);
        setIsProcessing(true);

        try {
          // 오디오 Blob 생성
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          console.log('[VoiceRecording] 녹음 완료, 크기:', audioBlob.size, 'bytes');

          if (audioBlob.size < 1000) {
            console.warn('[VoiceRecording] 녹음 데이터가 너무 작음');
            setError('녹음된 음성이 없습니다. 다시 시도해주세요.');
            setIsProcessing(false);
            resolve(null);
            return;
          }

          // REST API로 전송
          console.log('[VoiceRecording] API 전송 시작...');
          const response = await voiceApi.sendVoiceMessage(sessionId, audioBlob);
          console.log('[VoiceRecording] API 응답:', response);

          const result: VoiceRecordingResult = {
            userText: response.transcribed_text,
            aiResponse: {
              text: response.ai_message,
              intent: response.intent,
              suggestedAction: response.suggested_action,
              handoverStatus: response.handover_status || null,  // 핸드오버 상태 추가
            },
            audioBase64: response.audio_base64,
          };

          setIsProcessing(false);
          resolve(result);
        } catch (err) {
          console.error('[VoiceRecording] API 전송 실패:', err);
          setError('음성 처리 중 오류가 발생했습니다.');
          setIsProcessing(false);
          resolve(null);
        }

        // 스트림 정리
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
      };

      mediaRecorder.stop();
      console.log('[VoiceRecording] 녹음 중지 요청');
    });
  }, [sessionId]);

  return {
    isRecording,
    isProcessing,
    error,
    recordingTime,
    startRecording,
    stopRecording,
  };
};

export default useVoiceRecording;
