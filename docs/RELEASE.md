# 출시 및 배포 관리

문서에만 설계된 기능을 배포 완료로 간주하지 않으며, 실제 테스트/검증 근거에 따라 상태를 구분합니다.

## v0.1.x
- **상태:** [로컬 테스트 및 패키징 검증 완료]
- **구현 기능:**
  - 기본 CRM
  - 메시지 작업 생성
  - 수동 Agent 발송
  - 예약 시간 저장
  - 수동 Agent 기반 예약 작업 처리
  - Windows PC Agent 메모리 전용 JWT 인증 (`CMhelper_agent/api_client.py`, `CMhelper_agent/agent.py`)
  - Agent 명시적 UI 로그인 및 비밀번호 제출 즉시 위젯 삭제
  - Agent 401/403 Fail-Closed 토큰 무효화 및 재로그인 강제
  - 서버 상태 업데이트 성공 확인 후 로컬 성공 반영 (서버 권한 보존, 가짜 성공 방지)
  - PyInstaller 빌드 명세 (`CMhelper_agent/requirements-build.txt`, `CMhelper_agent/CMhelper_agent.spec` -> `CMhelper_agent.exe`)
  - Harness `cmhelper_pc_agent_auth` 검증 프로파일 (Agent 단위 테스트 및 격리 빌드 검증)
  - 카카오톡 UIA 어댑터 (`CMhelper_agent/kakao_ui.py`, `CMhelper_agent/agent.py`)
  - 채팅 탭 전용 탐색 및 상태 검증 (친구/친구추가/새채팅/Ctrl+2 배제)
  - 단일 일치(1건) 검증 및 창 제목 불일치/팝업 감지 시 Fail-Closed 차단
  - 모든 경로에서 `finally`를 통한 멱등한 검색어/상태 정리 (`cleanup_search()`, 카카오 데이터 보존)
  - 가짜 UI 객체 기반 단위 테스트 및 미발송 검증 (`CMhelper_agent/tests/test_kakao_ui.py`)
  - 단순 git revert 가능한 롤백(Rollback-by-Revert) 태세 유지

## 수동 사후 검증 절차 (Manual Post-Review Verification)
1. Agent 실행 후 이메일/비밀번호 로그인 UI 표시 및 비밀번호 입력 후 제출 시 즉시 위젯이 비워지는지 확인.
2. 잘못된 비밀번호 또는 비활성화 계정으로 로그인 시 401/403 오류가 발생하고 대기열 불러오기가 차단되는지 확인.
3. 올바른 계정으로 로그인 후 [대기열 불러오기]를 누르면 Bearer 토큰이 전달되어 정상적으로 대기열이 조회되는지 확인.
4. 발송 완료 또는 취소 시 서버에 인증된 상태 업데이트 요청이 전송되고, 서버 응답(200) 성공 시에만 로컬 UI 상태가 갱신되는지 확인.
5. `CMhelper_agent.exe` 빌드 결과물이 정상 생성되고 실행되는지 확인.
6. **카카오톡 UIA 및 전용 테스트 방 수동 QA (사후 검토 및 별도 명시적 승인 필요):**
   - 카카오톡 실행 후 전용 테스트 대화방(예: '테스트고객') 준비.
   - 발송 시작 시 UIA 어댑터가 채팅 탭을 정확히 선택하고 검색을 수행하는지 확인 (친구 탭/친구 추가 미선택).
   - 단일 일치 대화방 진입 및 전면 창 제목 검증 후 텍스트/이미지 순서로 정상 발송되는지 확인.
   - 모든 발송 시도 후 검색창 임시 텍스트가 깨끗이 초기화되는지 확인 (카카오 데이터 보존).
   - 미등록 고객 또는 동명이인(2건 이상) 존재 시 발송이 즉시 안전 실패(Fail-Closed) 처리되고 오발송이 발생하지 않는지 확인.

## 미구현 및 향후 기능 (Planned)
- Atomic Lock
- Heartbeat
- Recovery Queue
- Agent UUID
- Remote Config
- Canary Test
