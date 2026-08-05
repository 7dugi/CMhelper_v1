# API 명세서 (API Contract)

본 문서는 실제 `crud.py` 및 `main.py`에 구현된 Backend-Agent 통신 API 규격을 명시합니다. 구현되지 않은 API는 `[PLANNED]`로 표기합니다.

## 1. 대기 작업 선점 및 조회 (Agent -> Backend)
**`GET /api/messages/pending`**
- **기능:** 예약(RESERVED) 또는 복구(RECOVERY) 상태인 대기열을 조회함과 동시에 상태를 `PROCESSING`으로 변경(Atomic Lock).
- **Query Params:**
  - `agent_uuid` (string, required): 작업을 가져갈 로컬 에이전트의 고유 ID.
- **Response:**
  - `200 OK`: `List[MessageTaskOut]` 반환. `status`는 `PROCESSING`으로, `locked_by`는 `agent_uuid`로 변경된 상태로 반환됨.
- **동시성 처리 (Atomic Lock):** SQLite 한계상 다중 에이전트 동시 접근 시 완벽한 ROW 레벨 락(`SELECT FOR UPDATE`) 대신 `UPDATE ... WHERE id IN (...)` 구조를 사용하고 있으며, 추가적인 동시성 검증(스트레스 테스트)이 필요합니다.

## 2. Heartbeat 갱신 (Agent -> Backend)
**`PUT /api/messages/{task_id}/heartbeat`**
- **기능:** 에이전트가 처리 중인 작업의 생존 신호(`heartbeat_at`)를 갱신하여 고아(Orphan) 처리되는 것을 방지합니다.
- **Query Params:**
  - `agent_uuid` (string, required): 현재 작업을 선점한 에이전트 ID.
- **Response:**
  - `200 OK`: `{"detail": "Heartbeat updated"}`
  - `404 Not Found`: 작업이 없거나 현재 `agent_uuid`에 의해 `PROCESSING` 중이 아닐 때.

## 3. 작업 결과 보고 및 상태 전이 (Agent -> Backend)
**`PUT /api/messages/{task_id}/status`**
- **기능:** 발송 완료 또는 실패 시 최종 상태를 업데이트합니다.
- **Body:**
  - `status` (string): `SUCCESS`, `FAILED`, `RECOVERY` 등
  - `error_code` (string, optional): 에러 발생 시 사유
- **상태 전이(Retry) 처리 로직:**
  - 백엔드 `crud.py`에서 `status`가 `RECOVERY`나 `FAILED`로 요청될 때 내부적으로 `retry_count`를 1 증가시킵니다.
  - `retry_count >= 2`가 될 경우, 에이전트가 `RECOVERY`를 요청했더라도 백엔드에서 강제로 `FAILED`(`error_code="MAX_RETRY_EXCEEDED"`)로 전환하여 무한 루프를 방지합니다.

## 4. [PLANNED] Agent Remote Config (서버 설정 배포)
**`GET /api/agent/config`**
- **기능:** 카카오톡 UI 식별자, 버전 제한, Poll Interval 등을 백엔드에서 중앙 제어하기 위해 내려주는 설정 API (현재 미구현).
- **Response (예정):**
  - `200 OK`: `{"uia_targets": {...}, "min_version": "1.0.1", "poll_interval_ms": 30000}`
