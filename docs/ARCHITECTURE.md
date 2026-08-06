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

## Target Architecture [PLANNED]
- pywinauto 기반 UI 제어
- OpenCV Fallback
- API 인증
- 데이터 사용자별 격리
- Remote Config
- Canary Test
- PostgreSQL/Supabase DB 전환 여부
- Agent Auto Update

*참고: 상시 Agent, Windows Service, Tray Agent, Windows 자동 시작은 현재 목표에서 제외됨.*
