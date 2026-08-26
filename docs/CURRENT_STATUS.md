# 현재 상태

## 기준 브랜치
- main
- `feature/dev-harness-v1`에는 main에 아직 병합되지 않은 Phase 3D 기능이 포함되어 있다.

## 문서 동기화 상태
- 실제 main 구현 기준으로 정리됨
- 기능 브랜치의 미병합 기능은 [PLANNED] 또는 [FEATURE BRANCH ONLY] 로 구분한다.

## [FEATURE BRANCH ONLY] — Phase 3 영업 퍼널
- 인증 기반 및 OWNER/USER RBAC 기반
- Opportunity 및 Quote CRUD, 회사별 Tenant Isolation
- Opportunity/Quote Frontend 및 Runtime 검증
- WON Opportunity의 명시적 계약 전환
  - 계약 자동 생성 금지, 최종 `저장하기` 시에만 생성
  - 견적 0건 빈 계약 양식, 1건 자동 선택·사전 입력, 다건 견적 선택 후 사전 입력
  - 기존 수동 `+ 계약 추가` 및 계약 수정 CRUD 유지
- Phase 3D Part 1 Backend Foundation 및 Part 2A Frontend Conversion Workflow 완료

## [PLANNED] — 다음 제품 단계
- Phase 3E: Dashboard & Analytics (영업 퍼널, 전환율, 대시보드 위젯)
- 상세 데이터 모델·API·권한 범위는 Architecture Gate 승인 후 확정

## [IMPLEMENTED]
- 고객 등록 및 수정
- Excel 고객 데이터 가져오기
- 상담 메모 관리
- 웹에서 메시지 작업 생성
- Agent 수동 호출 (프로토콜 launch `cmhelper://start`는 창만 실행)
- Agent 메모리 전용 JWT 인증 (`CMhelper_agent/api_client.py`, `CMhelper_agent/agent.py`)
- Agent 명시적 이메일/비밀번호 UI 로그인 및 비밀번호 제출 즉시 클리어
- Agent 401/403 Fail-Closed 토큰 무효화 및 재로그인 요구
- Agent 대기열 불러오기 / 발송 / 취소의 Bearer 토큰 인증 연동
- 서버 상태 업데이트 성공 확인 후 로컬 성공 반영 (가짜 성공 방지)
- 수동 발송 시작
- 카카오톡 텍스트 발송
- 이미지 발송
- 창 제목 기반 고객 이름 1차 검증
- 예약 시간 저장
- Agent 수동 실행 후 예약 시간이 지난 작업 조회 및 발송
- pending / sent / failed 상태 처리
- Agent PyInstaller 빌드 명세 (`requirements-build.txt`, `CMhelper_agent.spec` -> `CMhelper_agent.exe`)
- Harness `cmhelper_pc_agent_auth` 검증 프로파일 (Agent 단위 테스트 및 격리 빌드 검증)
- 카카오톡 UIA 어댑터 (`CMhelper_agent/kakao_ui.py`):
  - `pywinauto` UIA 기반 카카오톡 메인 창 활성화 및 접근 가능한 이름 기반 채팅 탭 전용 탐색/상태 검증
  - 친구 탭, 친구 추가, 새로운 채팅, 고정 좌표 클릭, 이미지 매칭, `Ctrl+2` 단축키 엄격 배제
  - 채팅 검색창 활성화, 검색어 입력 및 정확히 1건의 기존 채팅방 일치 검증 (0건 또는 2건 이상 모호성 시 Fail-Closed)
  - 전면 대화창 제목 검증 (수신자명 불일치 시 창 닫기 및 Fail-Closed)
  - 모든 탐색 시도(정상, 실패, 취소, 예외) 후 `finally` 블록에서 멱등한 임시 검색 정리(`cleanup_search()`, 카카오 데이터 보존)
  - 자동화 단위 테스트 가짜 UI 객체 전용 검증 (`CMhelper_agent/tests/test_kakao_ui.py`, 메시지 미발송 검증)
  - 단순 git revert를 통한 롤백(Rollback-by-Revert) 태세 유지 및 사후 전용 테스트 방 수동 QA 경계 정의

## [PARTIALLY VERIFIED]
- 동명이인 구분 및 단일 채팅방 매칭
- 이미지 팝업 예외 처리
- 여러 카카오톡 버전 호환성
- 네트워크 장애 복구

## [PLANNED]
- OpenCV Fallback
- Remote Config
- Canary Test
- 인증 및 사용자별 데이터 분리 (JWT Access Token 전용, 만료 2시간)
- Sales Funnel
- Recipe / Template
- Customer Portal
- PROCESSING / RECOVERY / RESERVED / CANCELLED 상태 머신
- locked_by / heartbeat_at / retry_count / error_code
- Atomic Lock
- Heartbeat API
- Orphan Task Recovery
- Agent UUID 기반 작업 선점 (향후 API Key/Device Token 연동)
- TimedRotatingFileHandler 감사 로그

## [EXCLUDED FROM CURRENT SCOPE]
- JWT Refresh Token (Sprint B 이후 도입)
- Agent 자동 로그인 / 비밀번호·JWT 디스크/레지스트리 영속화 / Credential Manager
- Device Token / API Key 체계 (향후 별도 Architecture Gate 대상)
- Agent 상시 실행
- Windows Service
- Tray Agent
- Windows 자동 시작
- 무인 예약 발송
