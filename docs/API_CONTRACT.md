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

*인증 여부: 현재 모든 API는 인증 없음.*

## 2. 향후 계획 API [PLANNED]
- Heartbeat
- Atomic Claim
- Agent UUID 등록
- Remote Config
- Canary Test
- Recovery API
