# 변경 이력 (Changelog)

모든 주요 변경 사항은 이 문서에 기록됩니다. 기능은 실제로 코드에 구현되고 안정성이 검증된 것만 정식 버전에 기록합니다.

## [Unreleased]
- **[Feature]** 카카오톡 UIA 어댑터(`CMhelper_agent/kakao_ui.py`) 및 Fail-Closed 탐색/정리 체계
  - `CMhelper_agent/requirements.txt`: `pywinauto` 런타임 의존성 추가 (기존 라이브러리 버전 유지)
  - `CMhelper_agent/kakao_ui.py` 신설: UIAutomation 기반 카카오톡 메인 창 활성화, 접근 가능한 이름 기반 채팅 탭("채팅", "Chats") 전용 선택 및 상태 검증
  - 친구 탭, 친구 추가, 새로운 채팅, 고정 좌표 클릭, 이미지 매칭, `Ctrl+2` 단축키 사용 엄격 배제
  - 검색 결과 단일 일치(1건) 검증: 0건 또는 2건 이상(동명이인/중복), 팝업 감지, 타임아웃 발생 시 즉시 Fail-Closed로 발송 차단
  - 전면 대화창 제목 검증: 수신자명과 실제 창 제목 불일치 시 대화창을 닫고 안전 실패 처리
  - 모든 탐색 시도 후 `finally` 블록에서 멱등한 `cleanup_search()` 수행 (임시 검색어 삭제 및 상태 리셋, 카카오 데이터 보존)
  - `CMhelper_agent/agent.py`: 기존 고정 좌표/Ctrl+F 탐색 블록을 UIA 어댑터로 위임 및 `finally` 정리 연동 (기존 인증/발송/서버 상태 처리 보존)
  - `CMhelper_agent/tests/test_kakao_ui.py`: 가짜 UI 객체 기반 단위 테스트 추가 (채팅 탭 검증, 친구/친구추가 배제, 0건/다건 모호성, 팝업 차단, 제목 불일치, 멱등 정리, 미발송 검증)
  - `CMhelper_agent/CMhelper_agent.spec`: `pywinauto`, `kakao_ui` hidden import 추가
- **[Feature]** Windows PC Agent 메모리 전용 JWT 인증 및 Fail-Closed 보안 체계
  - `CMhelper_agent/api_client.py` 도입: `POST /api/auth/login` 로그인 및 프로세스 메모리 전용 JWT 보관
  - `CMhelper_agent/agent.py` UI 업데이트: 명시적 이메일/비밀번호 로그인, 제출 즉시 비밀번호 위젯 삭제, 미인증 시 대기열/발송/취소 동작 차단
  - 401/403 Fail-Closed 처리: 토큰 만료 또는 권한 오류 시 즉시 메모리 토큰 무효화 및 재로그인 강제
  - 서버 상태 업데이트(200) 확인 시에만 로컬 UI 성공 처리 (가짜 성공 방지 및 서버 권한 보존)
  - `CMhelper_agent/tests/test_agent_auth.py`: 가짜 데이터 기반 단위 테스트 추가 (로그인, 인증 헤더 전달, 401/403 무효화, 상태 실패 처리)
  - `CMhelper_agent/requirements-build.txt` 및 `CMhelper_agent/CMhelper_agent.spec`: `CMhelper_agent.exe` 독립 실행파일 빌드 명세화
  - Harness `cmhelper_pc_agent_auth` 검증 프로파일 추가: Agent 단위 테스트 및 격리 임시 디렉토리 기반 PyInstaller 빌드 검증
- **[Feature]** B2B SaaS 확장을 위한 인증 시스템 기반 구축 (feature/auth-foundation)
  - JWT 기반 회원가입, 로그인, `/auth/me` API 구현
  - User, Company DB 추가 및 상태(Enum) 도입
  - 서버 시작 시 필수 인증 환경변수 검증(Fail-Fast) 도입
  - pytest를 이용한 백엔드 독립 테스트 구성
- V4.1 엔터프라이즈 복구 기능 (Heartbeat, Orphan Task Recovery, Retry Limit, Audit Log Rotation 등)
- 다중 에이전트 동시 구동 시 SQLite `locked_by` 로직(Atomic Lock) 구현 계획

## [v0.1.0] - 2026-07-16
### Added
- 카카오톡 데스크톱 프로세스 인식 및 채팅방 진입 기능 (pyautogui 기반)
- 채팅방 이름과 발송 대상명 일치 여부 1차 검증
- `pyperclip` 클립보드 경유 방식의 텍스트 및 이미지 분리 전송 기능
- 백엔드(FastAPI) 고객 및 발송 큐(MessageTask) API 연동
- 예약 시간 등록 및 수동 Agent 실행 기반 예약 작업 처리
