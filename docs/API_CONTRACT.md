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

*인증 여부: 현재 위 API들은 JWT 인증이 필요합니다. 서버는 현재 사용자 기준으로 회사별 데이터 범위와 USER 담당자 범위를 강제합니다.*

## 2. Authentication API [IMPLEMENTED]
- **POST `/api/auth/register`**: 초대 코드 기반 회원가입
- **POST `/api/auth/login`**: 로그인 및 JWT 발급
  - *인증 방식:* Access Token 전용 (Refresh Token 미도입, Sprint B 이후 재검토)
  - *토큰 보관:* 웹 프론트엔드는 SessionStorage 보관, Windows PC Agent는 프로세스 메모리에만 보관
  - *만료 시간:* 2시간 (2 hours)
- **GET `/api/auth/me`**: 현재 로그인된 사용자 정보 조회 및 JWT 검증
- **Windows PC Agent 연동 [IMPLEMENTED]**:
  - Agent는 기존 `POST /api/auth/login`을 통해 이메일/비밀번호로 명시적 로그인합니다.
  - 발급된 JWT Access Token은 인스턴스/프로세스 메모리에만 보관되며, 디스크/레지스트리/환경변수 영속화 및 로그 출력이 금지됩니다.
  - 모든 대기열 조회(`GET /api/messages/pending`), 상태 업데이트(`PUT /api/messages/{task_id}/status`), 취소 요청 시 `Authorization: Bearer <token>` 헤더를 전달합니다.
  - 401/403 오류 수신 시 즉시 토큰을 무효화하고 발송 루프를 중단하며 재로그인을 요구합니다 (Fail-Closed).
  - 프로토콜 호출(`cmhelper://start`)은 창 실행만 수행하며, 자동 로그인이나 자동 발송을 수행하지 않습니다.
  - 서버 상태 업데이트(HTTP 200) 응답을 수신한 경우에만 로컬 UI에 발송 완료를 기록합니다.

## 3. 향후 계획 API [PLANNED]
- Heartbeat
- Atomic Claim
- Agent UUID 등록
- Remote Config
- Canary Test
- Recovery API
