# 아키텍처 및 환경 설정

## Current Architecture [IMPLEMENTED]
현재 시스템에 실제로 코드로 구현되어 작동(또는 테스트 대기) 중인 스택입니다.
- **Frontend**: React + Vite 기반 SPA 대시보드
- **Backend**: Python FastAPI 기반 API 서버
- **ORM**: SQLAlchemy
- **Database**: SQLite (로컬 개발 및 초기 배포용)
- **Local Agent**: Python (pywinauto, pyperclip, win32gui) 백그라운드 매크로 에이전트
- **Packaging**: PyInstaller (Windows 실행 파일 `agent.exe` 빌드)

### 데이터 흐름 (Data Flow)
```plaintext
Web Dashboard
    ↓ (API)
Job Queue (SQLite message_tasks)
    ↓ (Auto Polling 30s)
Local Agent (Atomic Lock & Processing)
    ↓ (pywinauto / clipboard)
KakaoTalk (PC)
```

## Target Architecture [PLANNED]
향후 B2B SaaS 확장을 위해 목표로 하는 기술 및 아키텍처입니다.
- **Production DB**: PostgreSQL / Supabase (클라우드 환경 대규모 트래픽 대응)
- **Authentication**: JWT 또는 Supabase Auth 기반 다중 사용자/테넌트 지원
- **Remote Config**: 서버 중앙 관리형 UI 식별자 및 에이전트 설정 배포
- **Monitoring**: Datadog 또는 Sentry를 통한 에이전트 에러/DPI 편차 실시간 모니터링
- **Canary Test**: 매일 오전 자동 테스트 파이프라인(가짜 데이터 발송 후 결과 검증)
- **Auto Update**: 로컬 에이전트의 자동 버전 감지 및 패치 다운로드 시스템

---
## 고정 개발 환경 사양 (Agent 측 필수 유지)
- **Python**: 3.10.x (64-bit 권장)
- **Target OS**: Windows 10/11
- **디스플레이 배율**: 100% (OpenCV 템플릿 매칭 기준 권장)
