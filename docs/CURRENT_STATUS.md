# 현재 상태 📍

기능이 존재하는 것과 정상 작동이 완전히 검증된 것을 명확히 구분합니다.

*   `[VERIFIED]`: 실제 코드 구현과 수동/운영 테스트 결과가 모두 확인된 기능
*   `[PARTIALLY VERIFIED]`: 코드는 있으나 동시성 등 특수 조건 테스트가 불충분한 기능
*   `[IN PROGRESS]`: 현재 작업 중인 기능
*   `[PLANNED]`: 문서에만 존재하고 아직 구현되지 않은 기능
*   `[KNOWN ISSUE]`: 현재 발생 중인 문제

---

## 1. 현재 활성화된 브랜치
- [ ] main (stable)
- [x] feature/enterprise-tracking (V4.1 엔터프라이즈 로직 수동 테스트 완료, 베타 대기)

## 2. 카카오톡 제어 및 발송
- `[VERIFIED]` 카카오톡 프로세스 탐색 및 메인 창 포커싱 (pywinauto)
- `[VERIFIED]` 채팅방 이름 검증(Final Validation) 및 텍스트/이미지 분리 전송
- `[VERIFIED]` PyInstaller 빌드본(.exe) 환경 내 카카오톡 제어 및 클립보드 복사 동작

## 3. 예약 발송 기능
- `[VERIFIED]` 예약 정보 및 예약 시간 DB 저장
- `[VERIFIED]` 예약 작업 조회
- `[VERIFIED]` Agent 수동 실행 후 (대기열을 직접 불러와서) 예약 작업 발송
- `[PLANNED]` Agent 자동 실행 (Windows 시작 시 등)
- `[PLANNED]` 예약 시간 자동 감지 및 사용자 개입 없는 완전 자동(무인) 발송
- `[PLANNED]` Windows 서비스 기반 Background Agent 구동
- `[PLANNED]` Agent 내 발송 상태별 색상 구분 등 시각적 UI 고도화

## 4. 엔터프라이즈 장애 복구 체계 (V4.1)
- `[VERIFIED]` Heartbeat 생존 신호 송수신
- `[VERIFIED]` 고아 작업(Orphan Task) 복구 로직 (에이전트 강제 종료 시 RECOVERY 전이)
- `[VERIFIED]` 최대 2회 자동 재시도 횟수 제한(Retry Limit) 로직
- `[VERIFIED]` 감사 로그(Audit Log) 생성 및 로테이션, 이름 마스킹, PII 미기록 처리
- `[PARTIALLY VERIFIED]` 다중 에이전트 환경의 DB Atomic Lock (로컬 다중 봇 락 경합 등 스트레스 테스트 미수행)

## 5. 운영 및 인프라
- `[PLANNED]` 카나리아 테스트(Canary Test) 파이프라인 구축
- `[PLANNED]` Remote Config 설정 백엔드 통합
- `[KNOWN ISSUE]` 디스플레이 해상도(DPI) 배율에 따른 일부 UI 제어 편차 가능성 (OpenCV 의존 시)
