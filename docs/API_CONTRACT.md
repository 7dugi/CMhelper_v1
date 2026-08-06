# API 명세서 (API Contract)

## 1. 구현된 API [IMPLEMENTED]

- **고객 CRUD**:
  - GET `/api/customers`
  - GET `/api/customers/{cid}`
  - POST `/api/customers`
  - PUT `/api/customers/{cid}`
  - DELETE `/api/customers/{cid}`
- **상담 CRUD**:
  - POST `/api/customers/{cid}/consultations`
  - DELETE `/api/consultations/{log_id}`
- **Excel Import**: POST `/api/excel/import`
- **파일 업로드**: POST `/api/upload`
- **메시지 작업**:
  - POST `/api/messages/queue`
  - GET `/api/messages/pending`
  - DELETE `/api/messages/pending`
  - GET `/api/messages/history`
  - PUT `/api/messages/{task_id}/status` (상태값: pending, sent, failed)

*인증 여부: 현재 위 API들은 인증 없이 사용됩니다.*

## 2. Authentication API [PLANNED]
- **POST `/api/auth/register`**: 초대 코드 기반 회원가입
- **POST `/api/auth/login`**: 로그인 및 JWT 발급
  - *인증 방식:* Access Token 전용 (Refresh Token 미도입, Sprint B 이후 재검토)
  - *토큰 보관:* 프론트엔드 SessionStorage 보관
  - *만료 시간:* 2시간 (2 hours)
- **GET `/api/auth/me`**: 현재 로그인된 사용자 정보 조회 및 JWT 검증
- **Windows Agent 예외**: 기존 Agent는 인증이 면제되며 위 1번의 기존 API를 그대로 사용합니다. (향후 API Key/Device Token 도입 예정)

## 3. 향후 계획 API [PLANNED]
- Heartbeat
- Atomic Claim
- Agent UUID 등록
- Remote Config
- Canary Test
- Recovery API
