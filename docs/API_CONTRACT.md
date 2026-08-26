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
  - *토큰 보관:* 웹 프론트엔드는 SessionStorage 보관
  - *만료 시간:* 2시간 (2 hours)
- **GET `/api/auth/me`**: 현재 로그인된 사용자 정보 조회 및 JWT 검증
- **Windows Agent 연동 상태**: 메시지 API 인증 적용 이후 기존 Agent 소스는 아직 JWT를 전달하지 않아 인증된 메시지 API를 사용할 수 없습니다. 다음 Agent 인증 작업에서 기존 로그인 API를 사용해 Access Token을 실행 중 메모리에만 보관하고 모든 메시지 요청에 Bearer 토큰을 전달합니다. 비밀번호·토큰의 파일 저장 및 로그 출력은 금지합니다. Device Token은 향후 별도 Architecture Gate 대상입니다.

## 3. 향후 계획 API [PLANNED]
- Heartbeat
- Atomic Claim
- Agent UUID 등록
- Remote Config
- Canary Test
- Recovery API
