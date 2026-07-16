# 현재 상태 📍

## 1. 현재 활성화된 브랜치
- [ ] main (stable)
- [x] feature/enterprise-tracking (V4.1 엔터프라이즈 기능 적용 완료)

## 2. 정상 작동 기능 (Green)
- [x] 카카오톡 프로세스 탐색 및 메인 창 포커싱 (pywinauto/단축키 Fallback)
- [x] 채팅방 이름 검증(Final Validation) 및 텍스트/이미지 분리 전송
- [x] 고아 작업(Orphan Task) 복구 및 Heartbeat 생존 신호 처리 (V4.1)
- [x] 다중 에이전트 환경의 Atomic Lock 및 중복 발송 방지 (V4.1)
- [x] 실패 상황 감지 및 최대 2회 자동 재시도 큐(Retry Queue) 편입 (V4.1)
- [x] 일자별 감사 로그(Audit Log) 로테이션 및 이름 마스킹 보안 (V4.1)
- [x] 예약 발송 Auto-Polling 연동 (V4.1)

## 3. 현재 발생 중인 버그 및 해결 과제 (Red)
- [ ] 디스플레이 해상도(DPI)에 따른 일부 좌표 편차 문제 모니터링 필요
- [ ] 카나리아 테스트(Canary Test) 파이프라인 구축 및 Remote Config 설정 반영 예정
