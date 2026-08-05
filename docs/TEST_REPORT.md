# V4.1 Manual Test Report

## Test Environment
- OS: Windows 10/11
- Python: 3.10.x
- PyInstaller: 적용 및 빌드 확인
- KakaoTalk Version: 최신 PC 버전
- Display Scaling: 100% (권장)
- Test Date: 2026-08-05
- Tested By: 로컬 엔지니어 (수동)

## Test Cases

### TC-001 예약 발송 (Scheduled Registration & Manual Trigger)
- 목적: 등록된 예약 정보를 DB에 저장하고, 예약 시간이 지난 시점에 수동으로 Agent 대기열을 갱신해 작업이 처리되는지 확인한다.
- 절차: 웹에서 가상의 미래 시간으로 예약 등록 -> 시간이 지난 후 Agent에서 대기열 불러오기 -> 발송 시작 클릭.
- 예상 결과: 대기열에 진입하여 성공적으로 발송 완료.
- 실제 결과: 예약 등록, 작업 조회, Agent 수동 실행 후 발송 모두 성공.
- 상태: **PASS** 
  *(단, 예약시간 자동 감지 및 상시 무인 자동 발송은 NOT IMPLEMENTED)*

### TC-002 Heartbeat
- 목적: Agent 발송 처리 중 백엔드로 생존 신호를 정상적으로 보내는지 확인한다.
- 절차: 발송 시작 후 네트워크 모니터나 DB의 `heartbeat_at` 필드 갱신 여부 관찰.
- 예상 결과: 발송 중 주기적으로 `heartbeat_at` 시간이 최신화됨.
- 실제 결과: `heartbeat_at` 정상 갱신 확인.
- 상태: **PASS**

### TC-003 Orphan Recovery
- 목적: Agent 프로세스가 예기치 않게 강제 종료되었을 때, 멈춘 작업이 복구(RECOVERY)되는지 확인한다.
- 절차: 발송 진입 직전 Agent 강제 종료 -> DB에서 5분 대기 -> 백엔드 복구 로직 발동 확인.
- 예상 결과: `PROCESSING` 상태로 멈춘 작업이 5분 뒤 `RECOVERY` 상태로 전이됨.
- 실제 결과: `RECOVERY` 상태 전이 확인.
- 상태: **PASS**

### TC-004 Retry Limit
- 목적: 무한 에러 루프를 막기 위해 실패/복구 카운트가 최대치(2회)를 초과하면 FAILED로 전이되는지 확인한다.
- 절차: 유효하지 않은 타겟 또는 고의 실패를 2회 유발.
- 예상 결과: `retry_count`가 2에 도달하면 `RECOVERY` 대신 `FAILED`(`MAX_RETRY_EXCEEDED`)로 변경됨.
- 실제 결과: 재시도 2회 초과 시 완벽한 FAILED 변경 확인.
- 상태: **PASS**

### TC-005 Audit Log
- 목적: 보안 정책에 따라 이름 마스킹, 번호 미기록 등 로그가 분리되어 저장되는지 확인한다.
- 절차: 발송 완료/실패 후 `agent.log` 파일 내용 열람.
- 예상 결과: 에러 사유와 첫/끝 글자만 표시된 이름(예: 홍*동)만 기록되며, 전화번호/원문은 없음.
- 실제 결과: 로그 파일 생성 및 마스킹(PII 제거) 정상 적용 확인.
- 상태: **PASS**

### TC-006 PyInstaller EXE
- 목적: 패키징된 실행 파일(.exe) 안에서도 카카오톡 제어 및 클립보드 사용이 원활한지 확인한다.
- 절차: `dist/CMhelper_agent.exe` 실행 -> 가짜 예약 건 발송 트리거.
- 예상 결과: 파이썬 스크립트 실행 때와 동일하게 윈도우 UI 접근, 카카오창 활성화, 붙여넣기가 됨.
- 실제 결과: `.exe` 환경에서 완벽하게 동작 확인.
- 상태: **PASS**

### TC-007 Atomic Lock
- 목적: 다중 에이전트 구동 시 동일한 작업을 중복 선점하지 못하게 방어한다.
- 절차: 2~3개의 에이전트를 동시 실행하여 락 경합 시뮬레이션.
- 예상 결과: 동일 ROW 선점 불가 확인.
- 실제 결과: **NOT TESTED** (단일 에이전트 환경에서만 테스트 완료. 다중 환경 스트레스 테스트 미수행)
- 상태: **NOT TESTED**

---

## Known Limitations
- 자동화 테스트(Pytest, E2E) 코드 없음.
- DPI 125% 이상 환경에서의 OpenCV 템플릿 매칭 편차 검증 필요.
- 예약 시간 자동 감지를 통한 Background 무인 발송 메커니즘 부재.

## Final Result
- **CONDITIONAL PASS** (단일 에이전트 및 수동 조작 기준 검증 완료, 완전 무인 자동화/동시성은 추가 과제)
