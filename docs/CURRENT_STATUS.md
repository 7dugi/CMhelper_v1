# 현재 상태

## 기준 브랜치
- main

## 문서 동기화 상태
- 실제 main 구현 기준으로 정리됨
- 기능 브랜치의 미병합 기능은 [PLANNED] 또는 [FEATURE BRANCH ONLY] 로 구분한다.

## [IMPLEMENTED]
- 고객 등록 및 수정
- Excel 고객 데이터 가져오기
- 상담 메모 관리
- 웹에서 메시지 작업 생성
- Agent 수동 호출
- Agent 대기열 불러오기
- 수동 발송 시작
- 카카오톡 텍스트 발송
- 이미지 발송
- 창 제목 기반 고객 이름 1차 검증
- 예약 시간 저장
- Agent 수동 실행 후 예약 시간이 지난 작업 조회 및 발송
- pending / sent / failed 상태 처리

## [PARTIALLY VERIFIED]
- 해상도별 좌표 안정성
- 동명이인 구분
- 여러 카카오톡 버전 호환성
- 이미지 팝업 예외 처리
- 네트워크 장애 복구

## [PLANNED]
- pywinauto 기반 UI 객체 제어
- OpenCV Fallback
- Remote Config
- Canary Test
- 인증 및 사용자별 데이터 분리 (JWT Access Token 전용, 만료 2시간)
- Sales Funnel
- Recipe / Template
- Customer Portal
- PROCESSING / RECOVERY / RESERVED / CANCELLED 상태 머신
- locked_by / heartbeat_at / retry_count / error_code
- Atomic Lock
- Heartbeat API
- Orphan Task Recovery
- Agent UUID 기반 작업 선점 (향후 API Key/Device Token 연동)
- TimedRotatingFileHandler 감사 로그

## [EXCLUDED FROM CURRENT SCOPE]
- JWT Refresh Token (Sprint B 이후 도입)
- Windows Agent JWT 인증 (기존 API 유지, 향후 API Key 도입)
- Agent 상시 실행
- Windows Service
- Tray Agent
- Windows 자동 시작
- 무인 예약 발송
