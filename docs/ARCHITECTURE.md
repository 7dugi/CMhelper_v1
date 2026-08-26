# 아키텍처 및 환경 설정

## Current Architecture [IMPLEMENTED]
- **Frontend**: React + Vite
- **Backend**: FastAPI
- **ORM**: SQLAlchemy
- **Database**: 현재 실제 database.py 기준 (SQLite)
- **File Storage**: Supabase Storage 또는 로컬 업로드
- **Local Agent**: Python + Tkinter + pyautogui + pyperclip + win32gui + api_client
- **Agent Execution**: 사용자 수동 실행 (프로토콜 launch `cmhelper://start`는 창만 띄우며 자동 로그인/자동 발송 없음)
- **Agent Authentication**:
  - UI 기반 명시적 로그인 (`POST /api/auth/login`)
  - JWT Access Token은 인스턴스/프로세스 메모리에만 보관 (디스크, 레지스트리, 환경변수 영속화 금지)
  - 비밀번호 입력 위젯은 로그인 요청 제출 즉시 클리어
  - 모든 대기열 조회(`GET /api/messages/pending`), 상태 변경(`PUT /api/messages/{task_id}/status`), 취소(`DELETE /api/messages/pending`) 요청에 `Authorization: Bearer <token>` 첨부
  - 401/403 응답 시 즉시 메모리 토큰을 무효화하고 발송 중단 및 재로그인 요구 (Fail-Closed)
  - 서버 상태 업데이트 성공 응답(200)을 수신한 경우에만 로컬 UI 성공 처리 (가짜 성공 방지 및 서버 권한 보존)
- **Messaging**: Agent에서 사용자가 발송 시작
- **Scheduling**: scheduled_at 기반 조회 (무인 자동 실행 아님)
- **Packaging & Build**: PyInstaller 기반 단일 실행파일 빌드 (`requirements-build.txt`, `CMhelper_agent.spec` -> `CMhelper_agent.exe`)
- **Harness Validation**: allowlisted `cmhelper_pc_agent_auth` 프로파일 (Agent 가짜 데이터 단위 테스트 및 격리 빌드 검증)

## Target Architecture [PLANNED]
- pywinauto 기반 UI 제어
- OpenCV Fallback
- 데이터 사용자별 격리 고도화
- Remote Config
- Canary Test
- PostgreSQL/Supabase DB 전환 여부
- Agent Auto Update

*참고: 상시 Agent, Windows Service, Tray Agent, Windows 자동 시작, Device Token/API Key 체계는 현재 목표에서 제외됨.*
