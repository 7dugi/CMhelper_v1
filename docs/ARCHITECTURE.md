# 아키텍처 및 환경 설정

## 1. 시스템 구조 (Hybrid) 및 데이터 흐름
- **Frontend:** React + Vite 기반 웹 대시보드
- **Backend:** Python (FastAPI/Flask 등) 기반 API 서버 + SQLite/Supabase
- **Local Agent:** Python + PyInstaller 기반의 PC 백그라운드 매크로 에이전트

### 데이터 흐름 (Data Flow)
```plaintext
Web Dashboard
    ↓
Job Queue
    ↓
Local Agent
    ↓
KakaoTalk
```
*(위 흐름에 따라 Audit Log, Retry Queue, Monitoring 로직이 에이전트와 백엔드 간에 상시 동기화됩니다.)*

## 2. 핵심 기술 스택
- 카카오톡 제어: `pywinauto` (고유 ID 제어 우선) + `OpenCV` (이미지 인식 보조)
- 검증 로직: `pyperclip` (클립보드 검증), `win32gui`

## 3. 고정 개발 환경 사양 (필수 유지)
- **Python:** 3.10.x (64-bit 권장)
- **Target OS:** Windows 10/11
- **디스플레이 배율:** 100% (OpenCV 템플릿 매칭 기준)
- **패키징:** PyInstaller 5.x 이상
