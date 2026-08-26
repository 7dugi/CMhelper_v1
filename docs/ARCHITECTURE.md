# 아키텍처 및 환경 설정

## Current Architecture [IMPLEMENTED]
- **Frontend**: React + Vite
- **Backend**: FastAPI
- **ORM**: SQLAlchemy
- **Database**: 현재 실제 database.py 기준 (SQLite)
- **File Storage**: Supabase Storage 또는 로컬 업로드
- **Local Agent**: Python + Tkinter + pyautogui + pyperclip + win32gui
- **Agent Execution**: 사용자 수동 실행
- **Messaging**: Agent에서 사용자가 발송 시작
- **Scheduling**: scheduled_at 기반 조회 (무인 자동 실행 아님)
- **Message API Security**: JWT 인증 및 회사별 Tenant Isolation 적용. 현재 Agent 소스는 인증 헤더를 전달하지 않아 이 API와 호환되지 않으며, Agent 인증 작업 전에는 실제 발송에 사용하지 않는다.

## Target Architecture [PLANNED]
- pywinauto 기반 UI 제어
- OpenCV Fallback
- Windows Agent의 기존 로그인 API 기반 JWT 인증(실행 중 메모리 보관, 비밀번호·토큰 영속화 금지)
- 데이터 사용자별 격리
- Remote Config
- Canary Test
- PostgreSQL/Supabase DB 전환 여부
- Agent Auto Update

*참고: 상시 Agent, Windows Service, Tray Agent, Windows 자동 시작은 현재 목표에서 제외됨.*
