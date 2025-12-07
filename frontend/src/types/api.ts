// API 타입 정의

export interface ChatRequest {
  session_id: string;
  user_message: string;
}

export interface SourceDocument {
  source: string;
  page: number;
  score: number;
}

export type IntentType = 'INFO_REQ' | 'COMPLAINT' | 'HUMAN_REQ';
export type ActionType = 'CONTINUE' | 'HANDOVER';
export type SentimentType = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';

export interface ChatResponse {
  ai_message: string;
  intent: IntentType;
  suggested_action: ActionType;
  source_documents: SourceDocument[];
  info_collection_complete: boolean;
}

export interface HandoverRequest {
  session_id: string;
  trigger_reason: string;
}

export interface KMSRecommendation {
  title: string;
  url: string;
  relevance_score: number;
}

export interface AnalysisResult {
  customer_sentiment: SentimentType;
  summary: string;
  extracted_keywords: string[];
  kms_recommendations: KMSRecommendation[];
}

export interface HandoverResponse {
  status: string;
  analysis_result: AnalysisResult;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  intent?: IntentType;
  suggested_action?: ActionType;
  source_documents?: SourceDocument[];
}

