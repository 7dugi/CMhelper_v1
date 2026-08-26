# 변경 이력 (Changelog)

모든 주요 변경 사항은 이 문서에 기록됩니다. 기능은 실제로 코드에 구현되고 안정성이 검증된 것만 정식 버전에 기록합니다.

## [Unreleased]
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
- pywinauto 기반 UI 제어 전환 계획
- V4.1 엔터프라이즈 복구 기능 (Heartbeat, Orphan Task Recovery, Retry Limit, Audit Log Rotation 등)
- 다중 에이전트 동시 구동 시 SQLite `locked_by` 로직(Atomic Lock) 구현 계획

## [v0.1.0] - 2026-07-16
### Added
- 카카오톡 데스크톱 프로세스 인식 및 채팅방 진입 기능 (pyautogui 기반)
- 채팅방 이름과 발송 대상명 일치 여부 1차 검증
- `pyperclip` 클립보드 경유 방식의 텍스트 및 이미지 분리 전송 기능
- 백엔드(FastAPI) 고객 및 발송 큐(MessageTask) API 연동
- 예약 시간 등록 및 수동 Agent 실행 기반 예약 작업 처리
