# Git Workflow 및 운영 규칙

## 1. 목적
Git 저장소를 항상 안정적으로 유지하고 AI(Codex, Claude Code, Antigravity)가 동일한 개발 규칙으로 협업하기 위한 운영 원칙입니다.

## 2. Branch 전략
- **main**: 항상 배포 가능한 안정 버전
- **feature/*** : 신규 기능 개발
- **fix/*** : 버그 수정
- **docs/*** : 문서 수정
- **chore/*** : 저장소 정리, .gitignore 수정, 빌드 산출물 제거, 기타 Git 관리
- **release/*** : 배포 준비

## 3. Commit 규칙
다음 Prefix를 사용하여 커밋의 목적을 명확히 합니다.
- `feat:` 새로운 기능 추가
- `fix:` 버그 수정
- `docs:` 문서 수정
- `refactor:` 기능 변경 없는 코드 리팩토링
- `test:` 테스트 코드 추가 및 수정
- `chore:` 빌드, 설정, 저장소 청소 등 기타 작업

**예시:**
- `feat: add kakao retry queue`
- `fix: resolve clipboard race condition`
- `docs: update architecture`
- `chore: stop tracking build artifacts`

## 4. 작업 시작 절차 및 Pull Request 규칙
- 모든 변경은 `feature`, `docs`, `chore` 브랜치에서 분리하여 작업합니다.
- `main` 브랜치에는 **직접 commit 하지 않습니다.**
- 작업 시작 전 다음 절차를 거칩니다:
  1. 작업 등급 분류 (Standard Gate 또는 Architecture Gate)
  2. Standard Gate 또는 Architecture Gate 계획서 작성
  3. 사용자 승인 획득
  4. 최신 `main`에서 작업 브랜치 생성
  5. 구현
  6. 테스트
  7. 결과 보고
  8. PR 생성
  9. 리뷰 및 Merge
- 모든 변경은 Pull Request를 통해 코드 및 문서 리뷰를 거친 후 Merge 해야 합니다.

## 5. Merge 규칙
Merge 전 반드시 아래 사항을 확인합니다.
- `git status` 및 `git diff --cached`를 통한 커밋 내역 점검
- 기능 코드 포함 여부 및 오작동 가능성 점검
- 빌드 파일이나 임시 파일 포함 여부 검증
- 문서와 코드 구현 정합성 일치 여부

## 6. Release 규칙
- Release는 오직 `main` 브랜치를 기준으로만 생성합니다.
- Release 전에는 반드시 다음 문서의 업데이트를 확인합니다.
  - `CURRENT_STATUS.md`
  - `RELEASE.md`
  - `CHANGELOG.md`

## 7. 긴급 Hotfix
긴급 장애 발생 시 다음 절차를 따릅니다.
1. `hotfix/*` 브랜치를 `main` 기반으로 생성하여 수정.
2. 검증 후 즉시 `main`으로 Merge 및 배포.
3. 필요 시 개발 중인 `feature` 브랜치들에도 해당 Hotfix 내용을 병합(Merge)하여 반영.

## 8. AI 작업 규칙
새로운 AI(Codex / Claude Code / Antigravity)가 작업을 시작하기 전에 반드시 읽어야 할 공식 프로젝트 문서의 순서입니다.
1. `.agents/AGENTS.md`
2. `docs/PROJECT_OVERVIEW.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DATA_MODEL.md`
5. `docs/API_CONTRACT.md`
6. `docs/CURRENT_STATUS.md`
7. `docs/TODO.md`
8. `docs/GIT_WORKFLOW.md`

**AI 에이전트 필수 준수 사항:**
AI는 위 문서를 모두 읽고 현재 상태를 요약한 뒤, 작업 계획을 사용자에게 먼저 제시해야 합니다. 사용자의 승인이 떨어진 이후에만 실제 코딩을 시작합니다.
