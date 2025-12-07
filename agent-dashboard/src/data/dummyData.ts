// 더미 데이터 - 상담원 대시보드용

// 상담원 정보
export const agentInfo = {
  id: 'AG001',
  name: '김상담',
  status: 'available' as 'available' | 'busy' | 'break' | 'offline',
  todayCalls: 47,
  avgHandleTime: '4:32',
  satisfaction: 4.7,
};

// 대기열 정보
export const queueInfo = {
  waiting: 3,
  avgWaitTime: '1:23',
  slaWarning: true,
  slaPercentage: 85,
};

// 현재 고객 정보
export const currentCustomer = {
  customerId: 'C20241207001',
  name: '홍길동',
  phone: '010-****-5678',
  isPrivacyAgreed: true,
  memberGrade: 'VIP',
  cardType: '하나 원큐 카드',
  lastContact: '2024-11-15',
};

// 최근 3개월 상담 이력
export const recentHistory = [
  {
    date: '2024-11-15',
    channel: '전화',
    category: '결제일 변경',
    summary: '결제일 15일에서 25일로 변경 요청 - 완료',
    agent: '박상담',
  },
  {
    date: '2024-10-22',
    channel: '앱',
    category: '한도 조회',
    summary: '카드 한도 조회 및 상향 문의',
    agent: 'AI봇',
  },
  {
    date: '2024-09-18',
    channel: '전화',
    category: '분실 신고',
    summary: '카드 분실 신고 후 재발급 요청 - 완료',
    agent: '이상담',
  },
];

// 현재 세션 정보
export const currentSession = {
  callId: 'CALL-20241207-001',
  callerNumber: '010-1234-5678',
  channel: '보이스봇',
  ivrPath: '1 → 2 → 상담원 연결',
  startTime: '14:23:15',
  duration: '03:42',
  transferReason: '복잡한 업무 처리 요청',
};

// AI 상담 요약 (보이스봇에서 전달받은 정보)
export const aiSummary = {
  summary: `고객이 카드 한도 상향을 요청하였습니다.
현재 한도 300만원에서 500만원으로 상향 희망.
소득 증빙 서류 제출 의향 있음.`,
  customerSentiment: 'neutral' as 'positive' | 'neutral' | 'negative',
  keywords: ['한도 상향', '소득 증빙', '500만원', '신용카드'],
  intentClassification: '한도 안내/변경',
  confidence: 0.92,
  collectedInfo: {
    inquiryType: '한도 상향',
    requestedLimit: '500만원',
    currentLimit: '300만원',
    documentReady: '소득증빙 제출 가능',
  },
};

// 추천 스크립트
export const recommendedScripts = [
  {
    id: 1,
    title: '한도 상향 안내',
    content: '고객님, 카드 한도 상향을 도와드리겠습니다. 현재 고객님의 신용카드 한도는 300만원입니다. 500만원으로 상향을 원하시는 거죠?',
  },
  {
    id: 2,
    title: '소득 증빙 안내',
    content: '한도 상향을 위해서는 소득 증빙 서류가 필요합니다. 재직증명서 또는 원천징수영수증을 하나원큐 앱에서 제출해 주시면 됩니다.',
  },
  {
    id: 3,
    title: '심사 기간 안내',
    content: '서류 제출 후 영업일 기준 2-3일 내 심사 결과를 문자로 안내드립니다.',
  },
];

// KMS 추천 문서
export const kmsDocuments = [
  {
    id: 'KMS001',
    title: '카드 한도 상향 프로세스',
    category: '한도',
    relevance: 0.95,
  },
  {
    id: 'KMS002',
    title: '소득 증빙 서류 종류 및 제출 방법',
    category: '서류',
    relevance: 0.88,
  },
  {
    id: 'KMS003',
    title: '한도 심사 기준 안내',
    category: '심사',
    relevance: 0.82,
  },
];

// 좌측 네비게이션 메뉴
export const navigationMenu = [
  {
    id: 'general',
    label: '일반 상담',
    icon: '💬',
    count: 12,
  },
  {
    id: 'limit',
    label: '한도',
    icon: '💳',
    count: 5,
  },
  {
    id: 'lost',
    label: '분실·도난',
    icon: '🔒',
    count: 2,
    urgent: true,
  },
  {
    id: 'dispute',
    label: '이의제기',
    icon: '⚠️',
    count: 1,
  },
];

// 실시간 대화 내역 (보이스봇 → 상담원 이관 후 실시간 대화)
export const liveConversation = [
  {
    id: 1,
    speaker: 'bot',
    message: '안녕하세요, 하나카드 AI 상담사입니다. 무엇을 도와드릴까요?',
    timestamp: '14:23:15',
  },
  {
    id: 2,
    speaker: 'customer',
    message: '카드 한도를 올리고 싶어요.',
    timestamp: '14:23:22',
  },
  {
    id: 3,
    speaker: 'bot',
    message: '카드 한도 상향을 원하시는군요. 현재 고객님의 카드 한도는 300만원입니다. 얼마로 상향을 원하시나요?',
    timestamp: '14:23:28',
  },
  {
    id: 4,
    speaker: 'customer',
    message: '500만원으로 올리고 싶은데요.',
    timestamp: '14:23:35',
  },
  {
    id: 5,
    speaker: 'bot',
    message: '500만원으로 한도 상향을 원하시는군요. 한도 상향을 위해서는 소득 증빙 서류가 필요합니다. 서류 제출이 가능하신가요?',
    timestamp: '14:23:42',
  },
  {
    id: 6,
    speaker: 'customer',
    message: '네, 제출할 수 있어요. 근데 어떻게 해야 하는지 잘 모르겠어서 상담원 연결해주세요.',
    timestamp: '14:23:55',
  },
  {
    id: 7,
    speaker: 'bot',
    message: '네, 상담원에게 연결해 드리겠습니다. 잠시만 기다려 주세요.',
    timestamp: '14:24:02',
  },
  {
    id: 8,
    speaker: 'system',
    message: '상담원 연결됨 - 김상담',
    timestamp: '14:24:15',
  },
  {
    id: 9,
    speaker: 'agent',
    message: '안녕하세요, 홍길동 고객님. 하나카드 김상담입니다. 카드 한도 상향 관련해서 도움이 필요하시다고요?',
    timestamp: '14:24:20',
  },
  {
    id: 10,
    speaker: 'customer',
    message: '네, 소득 증빙 서류를 어떻게 제출하는지 알려주세요.',
    timestamp: '14:24:32',
  },
];

// 대기 중인 상담 목록
export const waitingConsultations = [
  {
    id: 'W001',
    customerName: '이영희',
    waitTime: '2:15',
    category: '한도',
    priority: 'normal' as 'urgent' | 'high' | 'normal',
  },
  {
    id: 'W002',
    customerName: '박철수',
    waitTime: '1:42',
    category: '분실·도난',
    priority: 'urgent' as 'urgent' | 'high' | 'normal',
  },
  {
    id: 'W003',
    customerName: '최민지',
    waitTime: '0:58',
    category: '일반 상담',
    priority: 'normal' as 'urgent' | 'high' | 'normal',
  },
];
