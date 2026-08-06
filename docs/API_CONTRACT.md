# API 명세서 (API Contract)

## 1. 구현된 API [IMPLEMENTED]

- **인증 (Auth)** [FEATURE BRANCH ONLY]:
  - POST `/api/auth/register` (성공: 201, 실패: 403, 409, 422)
  - POST `/api/auth/login` (성공: 200, 실패: 401, 403)
  - GET `/api/auth/me` (성공: 200, 실패: 401, 403)
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

*인증 여부: 현재 모든 API는 인증 없음.*

## 2. 향후 계획 API [PLANNED]
- Heartbeat
- Atomic Claim
- Agent UUID 등록
- Remote Config
- Canary Test
- Recovery API
