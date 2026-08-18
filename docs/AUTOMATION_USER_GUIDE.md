# CMhelper Automation User Guide

본 가이드는 CMhelper Development Harness를 일상 개발에 사용하는 방법을 안내합니다.
Codex Project Operating Layer(H8.2.2)가 도입되어 PC와 Mobile 환경에서 안전한 AI 주도 개발이 가능합니다.

## 시나리오 A: PC 또는 Mobile Remote에서 새 개발 세션 시작

1. PC Codex 창이나 Mobile Remote에서 새 채팅 세션을 엽니다.
2. **"CMhelper 개발 계속하자. 프로젝트 Bootstrap부터 확인해"** 라고 입력합니다.
3. Codex가 자동으로 `python -m automation.control bootstrap --project cmhelper`를 실행하여 현재 Git 브랜치, 상태, 대기 Queue를 읽고 작업 컨텍스트와 프로젝트 상태를 복원(Bootstrap)합니다.
4. Codex가 요약 보고를 하면 다음 논의로 넘어갑니다. 이전 대화 전체를 복사할 필요가 없습니다.

## 시나리오 B: Operating Modes 적용 (DISCUSSION / SPEC / EXECUTE)

Codex는 사용자의 지시 의도에 따라 세 가지 모드로 동작합니다.
이 과정은 자연어 분류기가 강제로 모드를 구별하는 것이 아니라, Codex가 지침을 따르는 상태(Instruction-level enforced)입니다.
실제 Task 생성은 명시적인 CLI 실행 시에만 발생합니다 (Code-level safety gate 적용).

### 1. DISCUSSION 모드
- **의도:** 요구사항, 설계, 기능 변경 사항 등을 논의합니다.
- **예시:** "이 기능은 어떻게 만드는 게 좋을까? 로직 수정해 볼까?"
- **특징:** 파일이나 코드를 분석하지만, 실제 비즈니스 코드 수정이나 Task 등록은 하지 않습니다.

### 2. SPEC 모드
- **의도:** 논의 결과를 구체적인 구현 지시서(Task Specification)로 작성합니다.
- **예시:** "좋아. 지금 결정한 내용으로 Harness에 구현 지시서 만들어줘. 아직 실행은 하지 마."
- **특징:** 구현 범위, 테스트 계획, 제약사항 등을 문서화하고, 아직 실행(Harness 등록)하지는 않습니다.

### 3. EXECUTE 모드
- **의도:** 확정된 지시서를 Harness 파이프라인에 등록하여 구현을 시작합니다.
- **예시:** "확정. 이 지시서를 Harness 작업으로 등록하고 실행해."
- **특징:** 명시적인 실행 지시가 있을 때만 `python -m automation.control create --project cmhelper --file <task.md>`를 실행합니다.

## Context Freshness Gate (컨텍스트 최신성 확인)

EXECUTE 모드 진입 시 CLI 스크립트가 현재 프로젝트 상태 문서(`CURRENT_STATUS.md` 등)가 최신인지 검사하는 Code-level safety gate를 적용합니다.

- **FRESH:** 최신 상태. 작업을 즉시 큐에 등록합니다.
- **STALE / CONFLICT:** 최근 종료된 Task 내용이 상태 문서에 반영되지 않았거나, 커밋되지 않은 충돌 상태입니다. 큐 등록이 차단(Fail-Closed)됩니다.
- **처리 방법:** 이 경우, 사용자가 수동으로 문서를 최신화하거나 문서 갱신 Task를 먼저 생성해야만 다음 구현을 진행할 수 있습니다.

## 승인 (Approval) 및 Discord 대화형 알림

작업(Task)이 완료되어 COMMIT, PUSH 또는 PRODUCTION_DEPLOY 단계에 도달하면 Discord로 승인 요청 알림이 발송됩니다.
Discord 봇이 연결되어 있다면 (Discord Bot Token 사용), **모바일 Discord 앱에서 직접 [Approve(승인)] / [Reject(거절)] 버튼을 클릭하여 제어**할 수 있습니다.

- **Discord 원격 승인 (Interactive):** Discord 알림의 버튼을 클릭하면 봇이 즉시 승인을 처리하고, Supervisor가 자동으로 실행을 재개(Auto-Resume)합니다.
- **로컬 승인 (CLI):** `python -m automation.control approve <task_id> <approval_id>`
- **로컬 거절 (CLI):** `python -m automation.control reject <task_id> <approval_id>`

### 격리 승인 (Action Isolation)
안전한 Fail-Closed 원칙에 따라, 권한은 행위 단위로 격리되어 승인됩니다.
- **COMMIT 승인:** 로컬 Git 저장소에 커밋하는 것만 허용.
- **PUSH 승인:** 로컬 커밋을 원격 저장소에 업로드하는 것만 허용 (COMMIT 완료 후 별도 요청됨).

### Fail-Closed 복구 (Resume Policies)
진행 중 오류가 발생하거나 예상치 못한 중단이 발생할 경우, 상태는 안전을 위해 `FAILED_STALLED` 또는 `NEED_USER_DECISION`으로 되돌아갑니다. 승인 없이 자동으로 코드를 커밋하거나 푸시하지 않습니다.

## Quota Auto-Retry (API Rate Limit 대응)

외부 API 호출 제한(Rate Limit, 예: HTTP 429)이 발생하면 Task는 즉시 중단되지 않고 `WAITING_FOR_QUOTA` 상태로 진입합니다.
Supervisor는 지정된 백오프 알고리즘(예: 15분, 60분 간격)에 따라 할당량 복구를 주기적으로 검사(Quota Probe)하며, API 상태가 정상으로 확인되면 자동으로 Task를 재개합니다. 

## 봇 프로세스 라이프사이클 (Supervisor Integration)

Supervisor(`python -m automation.supervisor`)가 시작될 때 `.env`에 `DISCORD_BOT_TOKEN`이 설정되어 있다면, Supervisor가 자동으로 Discord Bot 데몬(`discord_bot.py`)을 백그라운드에서 실행합니다. PC가 재부팅되더라도 Supervisor만 실행하면 Discord 대화형 버튼 봇이 함께 구동됩니다.

## 모바일 Remote 환경에서 Supervisor 데몬 띄우기

Discord 원격 승인이 동작하려면 PC에 `Supervisor`가 켜져 있어야 합니다.
Codex에 다음과 같이 지시하면 PC에서 `Supervisor`와 `Discord Bot`을 백그라운드 데몬으로 띄워줍니다.
```bash
python -m automation.supervisor
```

## 스크립트 기반 수동 작업 조회 (Harness 상태 확인)

직접 상태를 확인하고 싶을 때는 다음 CLI 명령을 사용합니다.
- 상태(의사) 검사: `python -m automation.control doctor --project cmhelper`
- 현재 진행/대기 상태: `python -m automation.control status <task_id>`
