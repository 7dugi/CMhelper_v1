# 아키텍처 및 환경 설정

## Current Architecture [IMPLEMENTED]
- **Frontend**: React + Vite
- **Backend**: FastAPI
- **ORM**: SQLAlchemy
- **Database**: 현재 실제 database.py 기준 (SQLite)
- **File Storage**: Supabase Storage 또는 로컬 업로드
- **Local Agent**: Python + Tkinter + pywinauto (UIA 어댑터 `kakao_ui.py`) + pyautogui + pyperclip + win32gui + api_client
- **Agent Execution**: 사용자 수동 실행 (프로토콜 launch `cmhelper://start`는 창만 띄우며 자동 로그인/자동 발송 없음)
- **KakaoTalk UI Automation (UIA Adapter)**:
  - `CMhelper_agent/kakao_ui.py` 기반 UIAutomation 어댑터 도입 (채팅 탭 탐색, 검색, 1건 결과 진입, 창 제목 검증, 임시 검색 정리 전담)
  - 명시적 바운디드 상수: 5.0초 타임아웃, 최대 3회 재시도, 0.5초 간격
  - 접근 가능한 이름 기반 채팅 탭("채팅", "Chats") 전용 선택 및 상태 검증
  - 친구 탭("친구"), 친구 추가("친구추가"), 새로운 채팅, 고정 좌표 클릭, 이미지 매칭 자동화, `Ctrl+2` 단축키 엄격 배제
  - 검색 결과 단일 일치(1건) 검증: 0건 또는 2건 이상(동명이인/중복), 팝업 감지, 타임아웃 발생 시 즉시 Fail-Closed로 발송 차단
  - 전면 대화창 제목 검증: 수신자명과 제목 불일치 시 대화창을 닫고 Fail-Closed 처리
  - 모든 탐색 시도(정상 완료, 안전 실패, 취소, 예외) 후 `finally` 블록에서 멱등한 `cleanup_search()` 수행 (임시 검색어 삭제 및 상태 리셋, 카카오 데이터 보존)
  - 단위 테스트는 100% 가짜 UI 객체(FakeUIElement, FakeDesktop)로만 검증하여 테스트 중 실제 메시지 발송 원천 차단
  - 단순 git revert로 즉시 롤백 가능한(Rollback-by-Revert) 아키텍처 격리
- **Agent Authentication**:
  - UI 기반 명시적 로그인 (`POST /api/auth/login`)
  - JWT Access Token은 인스턴스/프로세스 메모리에만 보관 (디스크, 레지스트리, 환경변수 영속화 금지)
  - 비밀번호 입력 위젯은 로그인 요청 제출 즉시 클리어
  - 모든 대기열 조회(`GET /api/messages/pending`), 상태 변경(`PUT /api/messages/{task_id}/status`), 취소(`DELETE /api/messages/pending`) 요청에 `Authorization: Bearer <token>` 첨부
  - 401/403 응답 시 즉시 메모리 토큰을 무효화하고 발송 중단 및 재로그인 요구 (Fail-Closed)
  - 서버 상태 업데이트 성공 응답(200)을 수신한 경우에만 로컬 UI 성공 처리 (가짜 성공 방지 및 서버 권한 보존)
- **Messaging**: Agent에서 사용자가 발송 시작 (사후 검토 및 별도 명시적 승인 하에 전용 테스트 방에서만 1차 수동 발송 검증)
- **Scheduling**: scheduled_at 기반 조회 (무인 자동 실행 아님)
- **Packaging & Build**: PyInstaller 기반 단일 실행파일 빌드 (`requirements-build.txt`, `CMhelper_agent.spec` -> `CMhelper_agent.exe`)
- **Harness Validation**: allowlisted `cmhelper_pc_agent_auth` 프로파일 (Agent 가짜 데이터 단위 테스트 및 격리 빌드 검증)

## Target Architecture [PLANNED]
- OpenCV Fallback
- 데이터 사용자별 격리 고도화
- Remote Config
- Canary Test
- PostgreSQL/Supabase DB 전환 여부
- Agent Auto Update

*참고: 상시 Agent, Windows Service, Tray Agent, Windows 자동 시작, Device Token/API Key 체계는 현재 목표에서 제외됨.*
