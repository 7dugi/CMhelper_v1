# Project Onboarding Guide

이 가이드는 CMhelper Development Harness에 **새로운 프로젝트를 연동하는 표준 절차**를 설명합니다.
일반적인 프로젝트(Ordinary Project)의 경우 Harness Core 코드(`automation/` 폴더 내 파이썬 모듈)를 복사하거나 수정할 필요 없이 설정 파일만으로 온보딩을 완료하는 것을 목표로 합니다.
(단, 기존에 지원하지 않는 특수 프레임워크나 새로운 기술 스택을 위한 특수 Adapter가 필요한 경우에 한하여 Core/Plugin 확장이 필요할 수 있습니다.)

## 1. 전제 조건 (Prerequisites)
*   Harness Core가 설치된 동일 레포지토리 환경 또는 공용 런타임 환경
*   새 프로젝트의 루트 폴더 생성 (예: `my_new_project/`)

## 2. 프로젝트 문서 준비
새 프로젝트 폴더 내에 기본 거버넌스 문서와 마일스톤 문서를 생성합니다.
*   `PROJECT_OVERVIEW.md`
*   `CURRENT_STATUS.md`
*   `ROADMAP.md`
*   `TODO.md`
*   필요 시 `TECHNICAL_PRINCIPLES.md` 등

## 3. Project Config 생성
레포지토리 최상위의 `projects/` 디렉토리에 새로운 YAML 설정 파일을 만듭니다. (예: `projects/my_new_project.yaml`)

```yaml
project_id: my_new_project
project_name: "My New Project"
project_root: "../my_new_project"  # projects/ 디렉토리 기준 상대경로 또는 절대경로
repository: "username/my_new_project"
default_branch: "main"
development_branch: "feature/dev"

governance_docs:
  - "docs/TECHNICAL_PRINCIPLES.md"
roadmap_path: "ROADMAP.md"
current_status_path: "CURRENT_STATUS.md"
todo_path: "TODO.md"

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
**Config 파일(.yaml)에는 절대 Secret 값을 저장하지 마십시오.**

## 5. Doctor Health Check
터미널에서 Doctor 커맨드를 실행하여 프로젝트 설정이 제대로 로드되고 패스가 유효한지 확인합니다.
```bash
python -m automation.control doctor --project my_new_project
```

## 6. 첫 Task 인가 (Dry Run)
무해한(Synthetic) 테스트 Task를 생성하여 Harness가 제대로 파일을 읽고 라우팅하는지 확인합니다.
```bash
python -m automation.control create --project my_new_project --title "Onboarding Test" --description "Check if harness routes correctly."
```
상태를 조회합니다.
```bash
python -m automation.control status <task_id>
```

모든 절차를 통과했다면 추가적인 코드 수정 없이 새 프로젝트 자동화가 완성된 것입니다.
