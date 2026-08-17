# CMhelper Automation User Guide

이 가이드는 CMhelper Development Harness를 일상 개발에 사용하는 방법을 안내합니다.

## 시스템 개요
CMhelper Harness는 Task 큐, Supervisor 데몬, Planning/Review, 브라우저 QA, Discord 알림을 통합하여 자동화된 무인(Headless) 개발 파이프라인을 제공합니다. 개발자는 긴 프롬프트를 복붙하지 않고, 안전하게 CLI 또는 파일로 Task를 인가하고 승인(Approve)만 하면 됩니다.

## 시나리오 A. PC에서 ChatGPT와 작업할 때
1. 웹 브라우저에서 ChatGPT 대화창을 엽니다.
2. "CMhelper 프로젝트의 다음 작업을 진행해 줘"라고 기획/개발을 논의합니다.
3. ChatGPT가 `PROJECT_OVERVIEW.md`, `ROADMAP.md` 등을 확인하고 작업 지시서를 작성하도록 유도합니다.
4. 작성된 지시서를 로컬 파일(예: `task_instruction.md`)로 저장합니다. (참고: PC ChatGPT 웹은 로컬 명령어를 직접 실행할 수 없습니다.)
5. 사용자가 직접 CLI를 통해 아래 명령을 실행하여 큐에 추가해야 합니다:
   ```bash
   python -m automation.control create --project cmhelper --file task_instruction.md
   ```
   ```
6. 이후 작업은 백그라운드 데몬(Supervisor)이 자동으로 처리하며, Discord로 실시간 알림이 옵니다.

## 시나리오 B. Antigravity (Local IDE) 사용 시
1. Antigravity IDE를 열고 "작업을 시작해" 라고 명령합니다.
2. Antigravity는 직접 파일을 작성하고 `python -m automation.control create` 명령을 스스로 실행하여 Local Harness를 호출할 수 있습니다.

## 시나리오 B. 터미널에서 직접 Harness를 사용할 때
1. Task 내용을 담은 마크다운 파일 `task.md`를 작성합니다.
2. 직접 CLI를 실행합니다:
   ```bash
   python -m automation.control create --project cmhelper --file task.md
   ```
3. 상태 조회:
   ```bash
   python -m automation.control status <task_id>
   ```

## 시나리오 D. Remote 터미널에서 작업할 때
외부 기기나 Remote SSH를 통해 접속한 경우에도 위 C의 직접 CLI 명령어 체계를 동일하게 사용합니다.
작업을 `create --file`로 던져두고 로그아웃해도, 서버의 Supervisor 데몬이 자동으로 진행합니다. (현재 SSH나 API와 같은 Transport 계층은 별도로 구축되지 않았으며 CLI 인터페이스만 준비되어 있습니다.)

## 승인(Approval) 및 거절(Reject)
작업이 완료되어 COMMIT 또는 PUSH 단계에 도달하면 `WAITING_FOR_USER_APPROVAL` 상태가 되며 Discord로 알림이 옵니다.
*   **승인:** `python -m automation.control approve <task_id> <approval_id>`
*   **거절:** `python -m automation.control reject <task_id> <approval_id>`

## 시스템 상태 확인 (Doctor)
현재 시스템 설정, 의존성, 자격 증명이 정상인지 확인하려면:
```bash
python -m automation.control doctor --project cmhelper
```

## 예외 처리 (Troubleshooting)
*   **Quota 대기 상태 (`WAITING_FOR_QUOTA`)**: AI 제공자의 쿼터를 다 쓴 경우입니다. 시스템이 자동 재시도하므로 대기하면 됩니다.
*   **FAILED_STALLED**: 테스트 실패, 빌드 에러, 리뷰 3회 이상 실패 등의 이유로 파이프라인이 멈춘 상태입니다. 원인을 직접 수정하고 `python -m automation.control resume <task_id>`로 재개해야 합니다.
*   **Windows 자동 시작 제한**: 보안 정책 상 관리자 권한 없이는 로그인 시 자동 시작(AtLogOn)이 불가능합니다. Daily 00:00으로 설정된 스케줄된 작업을 사용하거나 수동으로 시작해야 할 수 있습니다.

## Context Freshness Warning
Resolver는 Context Bundle을 기준으로 정상 판단하지만, 프로젝트 문서가 실제 Git 개발 상태보다 오래되면 과거 작업을 Next Task로 추천할 수 있습니다.
Before automatic next-task execution:
- ROADMAP
- CURRENT_STATUS
- TODO
- PROJECT_OVERVIEW
등 ProjectConfig가 지정한 핵심 상태 문서의 최신성을 확인해야 합니다.
