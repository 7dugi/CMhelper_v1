# CMhelper 런북 (Runbook)

이 문서는 실무자(엔지니어/운영자)가 시스템 장애 발생 시 즉각적으로 따라야 하는 실제 **실행 절차**와 확인 항목, 명령어, 롤백 절차를 기술합니다.

## 1. P1 장애: 로컬 Agent 전면 발송 불가 (카카오톡 업데이트 등)

### 1단계: 상황 파악 및 확산 방지
1. 백엔드 대시보드 접속 후 **[발송 예약 큐 일시정지 (Freeze)]** 기능 활성화 (실제 API 미구현 시 수동으로 DB `status='PAUSED'` 처리).
2. 카카오톡 최신 릴리즈 노트 또는 자동 업데이트 강제 적용 여부 확인.

### 2단계: 에이전트 긴급 롤백 및 Fallback
1. UI 식별자 변경 문제인 경우 백엔드의 `Remote Config` 값 수정 배포 (현재 미구현).
2. 구조적 변경일 경우 기존 에이전트 소스코드의 Fallback 플래그(OpenCV 강제 활성화)를 켜서 핫픽스 빌드.
   ```bash
   # Agent 빌드 스크립트 실행
   cd CMhelper_agent
   pyinstaller agent.spec --clean
   ```

### 3단계: 복구 확인
1. 로컬 환경에서 테스트 계정(가짜 데이터)으로 3회 이상 정상 발송(텍스트+이미지)되는지 수동 테스트 진행.
2. 검증 완료 시 핫픽스 에이전트 배포 및 예약 큐(Freeze) 해제.

## 2. P2 장애: 일부 고객 지속적 실패 (해상도, UI 오류 등)

### 1단계: 로그 및 영향 범위 파악
1. 문제 고객 PC의 로컬 로그 파일 수집: `C:\CMhelper_v1\CMhelper_agent\logs\agent.log`
2. 로그 내 `[FAILED]` 또는 `error_code` 내용 확인 (예: `ERR_NAME_MISMATCH`, `ERR_CLIPBOARD_LOCKED`).

### 2단계: 조치 및 데이터 보존
1. 최대 재시도(Retry Count >= 2)를 초과해 `FAILED`로 빠진 고객 데이터 리스트 확보 (`MessageTask` DB 조회).
2. DPI 문제인 경우 사용자에게 디스플레이 배율 100% 설정 우회 절차(Workaround) 안내.
3. 문제 해결 후 `FAILED` 데이터를 `RESERVED`로 수동 롤백 업데이트 처리.

## 3. P3/P4 장애: UI 및 기타 오류 대응

1. 핫픽스가 불필요한 사안은 백로그에 티켓 생성 후 정상 운영 유지.
2. 프론트엔드/백엔드 배포:
   - 프론트엔드: `npm run build` 후 배포 서버 동기화.
   - 백엔드: FastAPI 무중단 재시작 프로세스 (예: `systemctl restart cmhelper_api`).
