# V4.1 Manual Test Report

## Test Environment
- OS: Windows 10/11
- Python: 3.10.x
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
- 실제 결과: **NOT IMPLEMENTED** (현재 main 브랜치 기준 해당 로직 없음)
- 상태: NOT TESTED

### TC-003 Orphan Recovery
- 목적: Agent 프로세스가 예기치 않게 강제 종료되었을 때, 멈춘 작업이 복구(RECOVERY)되는지 확인한다.
- 실제 결과: **NOT IMPLEMENTED** (현재 main 브랜치 기준 RECOVERY 상태 없음)
- 상태: NOT TESTED

### TC-004 Retry Limit
- 목적: 무한 에러 루프를 막기 위해 실패/복구 카운트가 최대치(2회)를 초과하면 FAILED로 전이되는지 확인한다.
- 실제 결과: **NOT IMPLEMENTED** (현재 main 브랜치 기준 카운트 필드 없음)
- 상태: NOT TESTED

### TC-005 Audit Log
- 목적: 보안 정책에 따라 이름 마스킹, 번호 미기록 등 로그가 분리되어 저장되는지 확인한다.
- 실제 결과: **NOT IMPLEMENTED** (현재 main 브랜치 기준 해당 로직 없음)
- 상태: NOT TESTED

### TC-007 Atomic Lock
- 목적: 다중 에이전트 구동 시 동일한 작업을 중복 선점하지 못하게 방어한다.
- 실제 결과: **NOT IMPLEMENTED** (현재 main 브랜치 기준 locked_by 없음)
- 상태: NOT TESTED

---

## Known Limitations
- V4.1 기능(Heartbeat, Recovery 등)은 현재 기능 브랜치(`feature/agent-pywinauto-upgrade`)에서만 개발 중이며 `main` 브랜치에는 미반영.
- 예약 시간 자동 감지를 통한 Background 무인 발송 메커니즘 부재.

## Final Result
- **CONDITIONAL PASS** (단일 에이전트 및 수동 조작 기준 검증 완료, V4.1 복구/자동화 기능은 main 기준 모두 미구현)
