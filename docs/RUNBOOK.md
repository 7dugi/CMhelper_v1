# CMhelper Runbook

## 장애 대응 절차

### 1. 카카오톡 UI 변경 발생 시 대응 절차
1. 영향 범위 파악 (Canary Test 실패 알림 확인 등)
2. 변경된 UI 식별자 획득 (UIA Dump 또는 OpenCV 좌표)
3. 서버의 Remote Config 업데이트
4. 에이전트 재시작 유도 및 모니터링

### 2. 에이전트가 모두 FAILED 발생 시 대응 절차
1. 서버 DB 상태 확인 (MessageTasks 테이블 error_code 분석)
2. 카카오톡 자체 점검 또는 API 서버 연결 상태 확인
3. 필요 시 Fallback (OpenCV) 강제 활성화 (Remote Config 튜닝)
4. 장애 원인 해소 후 FAILED 건들을 RESERVED로 롤백 처리 (수동 스크립트)

### 3. Heartbeat 장애 발생 시 대응 절차
1. 서버가 PROCESSING 상태를 RECOVERY로 자동 전환했는지 DB 확인
2. Agent PC의 네트워크 단절 또는 전원 꺼짐 여부 확인
3. 에이전트 재기동 시 정상적으로 RECOVERY 건을 재수행하는지 모니터링

### 4. DB 복구 절차
1. 매일 자정 생성되는 DB 자동 백업본 확인
2. 백업본 복원 전, 최신 로컬 Audit Log 파일 교차 검증을 통해 유실된 트랜잭션 수동 복구
3. 애플리케이션 서비스 내리기 (점검 모드) -> DB 복원 -> 서비스 재가동
