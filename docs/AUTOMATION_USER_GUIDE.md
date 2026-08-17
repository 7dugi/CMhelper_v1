# CMhelper Automation User Guide

이 가이드는 CMhelper Development Harness를 일상 개발에 사용하는 방법을 안내합니다.
Codex Project Operating Layer(H8.2)가 도입되어 PC와 Mobile 환경에서 원활한 AI 주도 개발이 가능합니다.

## 시나리오 A: PC 또는 Mobile Remote에서 새 개발 대화 시작

1. PC Codex 창이나 Mobile Remote에서 새 채팅 세션을 엽니다.
2. **"CMhelper 개발 계속하자. 프로젝트 Bootstrap부터 확인해."** 라고 입력합니다.
3. Codex가 자동으로 `python -m automation.control bootstrap --project cmhelper`를 실행하여 현재 Git 브랜치, 상태, 큐(Queue)에 있는 작업 등 프로젝트의 상태를 복원(Bootstrap)합니다.
4. Codex가 요약 보고를 하면 다음 논의를 이어갑니다. 이전 대화 전체를 복사할 필요가 없습니다.

## 시나리오 B: Operating Modes 사용 (DISCUSSION / SPEC / EXECUTE)

Codex는 사용자의 지시 의도에 따라 세 가지 모드로 동작합니다.
자연어 분류기가 강제로 모드를 판별하는 것은 아니며, Codex가 지침을 따르는 형태(Instruction-level enforced)입니다.
실제 Task 생성은 명시적인 CLI 실행 시에만 발생합니다 (Code-level safety gate 적용).

### 1. DISCUSSION 모드
- **용도:** 요구사항, 설계, 기능 변경, 대안 등을 논의합니다.
- **예시:** "이 기능을 어떻게 만드는 게 좋을까? 아직 수정하지 마."
- **특징:** 파일이나 코드를 분석하지만, 실제 비즈니스 코드 수정이나 Task 등록은 하지 않습니다 (Instruction-level enforced).

### 2. SPEC 모드
- **용도:** 논의 결과를 구체적인 구현 지시서(Task Specification)로 작성합니다.
- **예시:** "좋아. 지금 결정한 내용으로 Harness용 구현 지시서 만들어줘. 아직 실행하지 마."
- **특징:** 구현 범위, 테스트 계획, 제약사항 등을 문서화하며, 아직 실행(Harness 등록)하지는 않습니다 (Instruction-level enforced).

### 3. EXECUTE 모드
- **용도:** 확정된 지시서를 Harness 파이프라인에 등록하여 구현을 시작합니다.
- **예시:** "확정. 이 지시서를 Harness 작업으로 등록하고 실행해."
- **특징:** 명시적 실행 지시가 있을 때만 `python -m automation.control create --project cmhelper --file <task.md>`를 실행합니다.
- **제한:** "좋아, 이 방향으로 가자."와 같은 애매한 표현으로는 자동 EXECUTE되지 않습니다. 반드시 명시적인 명령이 필요합니다.

## Context Freshness Gate (컨텍스트 최신화 확인)

EXECUTE 모드 진입 시, CLI 시스템은 현재 프로젝트 상태 문서(`CURRENT_STATUS.md` 등)가 최신인지 검사하는 Code-level safety gate를 적용합니다.

- **FRESH:** 최신 상태. 작업이 즉시 큐에 등록됩니다.
- **STALE / CONFLICT / UNKNOWN:** 최근 완료된 Task 내용이 상태 문서에 반영되지 않았거나, 커밋되지 않은 충돌 상태입니다. 큐 등록이 차단(Fail-Closed)됩니다.
- **처리 방법:** 이 경우, 사용자가 수동으로 문서를 최신화하거나 문서 갱신 Task를 먼저 생성하여야 다음 구현을 진행할 수 있습니다.
- **참고:** 작업 완료 후 상태 문서를 확인하고 갱신하는 것은 필수 규칙입니다(단, 전략적인 Roadmap 변경은 반드시 사용자 승인 필요).

## 승인 (Approval) 및 Discord 확인

작업(Task)이 완료되어 COMMIT 또는 PUSH 단계에 도달하면 Discord로 승인 요청 알림이 발송됩니다.
승인은 CLI를 통해 수동으로 처리해야 합니다:
- **승인 (Approve):** `python -m automation.control approve <task_id> <approval_id>`
- **거절 (Reject):** `python -m automation.control reject <task_id> <approval_id>`

## 새로운 프로젝트 추가

향후 다른 프로젝트(예: `project_b`)를 Harness에 추가하려면:
1. `projects/project_b.yaml` 환경 설정 파일을 생성합니다.
2. `OperatingLayerConfig` 항목에 프로젝트 문서(`context_sources`, `status_sources` 등)를 지정합니다.
3. Codex에서 **"Project B 개발 시작하자"** 라고 요청하면 동일한 Bootstrap과 운영 모드가 적용됩니다.

## Mobile Remote 사용

현재 ChatGPT Mobile 앱에서 "CMhelper 개발 계속하자" 라고 요청하면, 동일하게 PC Repository Context를 사용하는 Codex Project Operating Layer를 호출할 수 있습니다.
모바일 사용자는 별도의 SSH, HTTP 브릿지 없이 모바일에서 DISCUSSION, SPEC, EXECUTE 지시를 내리고 Harness 작업을 시작할 수 있습니다.

## 스크립트 기반 수동 작업 조회 (Harness 상태 확인)

직접 상태를 점검하고 싶을 때는 다음 CLI 명령을 사용합니다.
- 상태(의사) 검진: `python -m automation.control doctor --project cmhelper`
- 현재 진행/큐 상태: `python -m automation.control status <task_id>`
