# Project Onboarding Guide

이 가이드는 CMhelper Development Harness에 **새로운 프로젝트를 연동하는 전체 절차**를 설명합니다.
일반적인 프로젝트(Ordinary Project)의 경우 Harness Core 코드(`automation/` 폴더 내의 파이썬 모듈)를 복사하거나 수정할 필요 없이 설정 파일만으로 연동을 완료하는 것을 목표로 합니다.
(단, 기존에 지원하지 않는 특수 프레임워크나 배포 기술 선택에 따른 특수 Adapter가 필요한 경우에는 하위 Core/Plugin 확장이 필요할 수 있습니다.)

## 1. 전제 조건 (Prerequisites)
*   Harness Core가 위치한 단일 리포지토리 환경 또는 공용 서버 환경
*   새 프로젝트의 루트 폴더 생성 (예: `my_new_project/`)

## 2. 프로젝트 문서 준비
새 프로젝트 폴더 내에 기본 거버넌스 문서와 마일스톤 문서를 작성합니다.
*   `PROJECT_OVERVIEW.md`
*   `CURRENT_STATUS.md`
*   `ROADMAP.md`
*   `TODO.md`
*   (필요 시) `TECHNICAL_PRINCIPLES.md` 등

## 3. Project Config 생성
리포지토리 최상위의 `projects/` 디렉토리에 새로운 YAML 설정 파일을 만듭니다. (예: `projects/my_new_project.yaml`)

```yaml
project_id: my_new_project
project_name: "My New Project"
project_root: "../my_new_project"  # projects/ 디렉토리 기준 상대경로 또는 절대경로
repository: "username/my_new_project"
default_branch: "main"
development_branch: "feature/dev"

# H8.2부터 Operating Layer Config를 필수로 정의합니다.
operating_layer:
  context_sources:
    - "docs/PROJECT_OVERVIEW.md"
  status_sources:
    - "docs/CURRENT_STATUS.md"
    - "docs/ROADMAP.md"
    - "docs/TODO.md"
  rule_sources:
    - "docs/TECHNICAL_PRINCIPLES.md"
  harness_docs:
    - "docs/AUTOMATION_USER_GUIDE.md"
  freshness_sources:
    - "docs/CURRENT_STATUS.md"
    - "docs/ROADMAP.md"

supabase:
  enabled: false
  
vercel:
  enabled: true
  config:
    project: "my-new-project-web"
    
browser_qa:
  enabled: true
  config: {}

test_commands:
  - "npm run test"
build_commands:
  - "npm run build"
```

## 4. Secret 환경변수 설정
새 프로젝트에서 Supabase나 Vercel을 사용한다면 기존과 동일하게 시스템 환경변수(또는 `.env.local`)에 관련 토큰과 비밀번호를 세팅해야 합니다.
**Config 파일(.yaml)에는 절대 Secret 값을 포함하지 마십시오.**

## 5. Doctor Health Check
터미널에서 Doctor 커맨드를 실행하여 프로젝트 설정이 잘 로드되고 패스가 유효한지 확인합니다.
```bash
python -m automation.control doctor --project my_new_project
```

## 6. 새 프로젝트의 Codex Session Bootstrap
새 프로젝트를 연동한 뒤 Codex나 ChatGPT로 새로운 개발을 시작할 때는 다음 명령을 통해 Session Bootstrap을 수행해야 합니다.
```bash
python -m automation.control bootstrap --project my_new_project
```
이후 Codex가 상태를 인지하고 `DISCUSSION`, `SPEC`, `EXECUTE` 모드를 사용하여 무인 개발 사이클을 시작할 수 있습니다.

## 7. 첫 Task 생성 (Dry Run)
무해한(Synthetic) 테스트 Task를 생성하여 Harness가 제대로 파일을 읽고 라우팅하는지 확인합니다.
```bash
python -m automation.control create --project my_new_project --file dummy_task.md
```
상태를 조회합니다.
```bash
python -m automation.control status <task_id>
```

모든 절차를 통과했다면 추가적인 코드 수정 없이 새 프로젝트 연동이 완성된 것입니다.
