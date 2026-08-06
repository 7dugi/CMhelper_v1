# 변경 이력 (Changelog)

모든 주요 변경 사항은 이 문서에 기록됩니다. 기능은 실제로 코드에 구현되고 안정성이 검증된 것만 정식 버전에 기록합니다.

## [Unreleased]
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
