# 📋 브라우저 콘솔 Object 확인 방법

## 현재 상황

브라우저 콘솔에 많은 `▶ Object` 로그가 보이지만 펼쳐지지 않았습니다.

## ✅ 확인 방법

### 1. "상담된 리포트 수신:" Object 펼치기

콘솔에서 다음 로그를 찾아주세요:
```
상담된 리포트 수신: ▶ Object
```

**이 Object를 클릭해서 펼쳐주세요!**

내부에 다음 필드들이 있는지 확인:
```javascript
{
  status: "success",
  customer_sentiment: "NEUTRAL",
  summary: "???",  // ← 이 값 확인!
  extracted_keywords: [...],
  kms_recommendations: [...]
}
```

### 2. 직접 로그 출력

브라우저 콘솔에서 다음 명령어 실행:
```javascript
// 마지막으로 수신한 메시지 확인
console.log('마지막 메시지:', JSON.stringify(lastMessage, null, 2));
```

---

## 🔧 임시 해결: 프론트엔드 로깅 강화

프론트엔드에서 summary 값을 직접 출력하도록 수정하겠습니다.

