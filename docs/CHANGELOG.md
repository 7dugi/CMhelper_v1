# 업데이트 이력 (CHANGELOG)

## [v0.4.1] - 2026-07-16
### Added
- **엔터프라이즈급 장애 복구 시스템**: 에이전트 UUID 및 Heartbeat 메커니즘을 추가하여 비정상 종료 시 Orphan Task를 `RECOVERY` 상태로 자동 복구합니다.
- **원자적 상태 잠금 (Atomic Lock)**: DB 레벨에서 상태를 제어하여 다중 에이전트 간 경쟁 조건을 방지했습니다.
- **Auto-Polling 및 예약 발송 완벽 연동**: 30초마다 대기열을 체크하며, 예약된 시간에 맞게 상태를 업데이트하고 에이전트가 처리합니다.
- **감사 로그(Audit Log) 로테이션 및 보안**: Python `logging`의 `TimedRotatingFileHandler`를 활용해 로그를 30일간 보관하며, 이름 마스킹(예: 홍*동)을 지원합니다.
- **재시도 로직 강화**: 에러(클립보드 점유 실패, 방 찾기 실패) 발생 시 2회까지 `RECOVERY` 큐에서 자동 재시도합니다.
### Changed
- 데이터베이스 `message_tasks` 테이블에 `locked_by`, `locked_at`, `heartbeat_at`, `retry_count`, `error_code` 컬럼 추가 (DB 마이그레이션).
- 프론트엔드 버튼 텍스트("N명에게 예약 발송하기") 및 상태 시각화 아이콘(⚪ 🟡 🟠 🟢 🔴 ⚫) 개편.
- 발송 상태명을 전부 대문자로 통합 (`RESERVED`, `PROCESSING`, `RECOVERY`, `SUCCESS`, `FAILED`, `CANCELLED`).

## [v0.1.1] - 2026-07-15
### Fixed
- 카카오톡 채팅방에서 두 번째 메시지 전송 시 기존 검색어가 지워지지 않는 문제 수정.
- 이미지 전송 팝업 시 텍스트가 미전송되는 꼬임 현상을, '이미지 우선 발송 후 텍스트 발송' 순서로 변경하여 해결.

## [v0.1.0] - 2026-07-15
### Added
- 카카오톡 초기 자동화 기본 로직 구현 완료.
