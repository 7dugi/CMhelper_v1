# CMhelper 개발 사전 검증 절차 (Development Gate)

이 문서는 모든 AI 에이전트와 개발자가 기능 구현 전에 따라야 하는 공식 계획·검증·승인 절차입니다.

## 1. 목적

- 실제 코드와 문서를 확인하지 않은 추상적 계획 방지
- 기존 기술 스택과 충돌하는 신규 라이브러리 도입 방지
- DB/API/보안/배포/테스트 누락 방지
- 기존 기능과의 중복·모순 방지
- Architecture Gate 계획서의 반복 수정 최소화
- 구현 전에 위험과 롤백 방법 확정
- 현재 구현과 미래 계획의 혼동 방지

## 2. 작업 등급 분류

모든 작업은 구현 전에 다음 두 등급 중 하나로 분류합니다.

### A. Standard Gate

**적용 대상:**
- 문구 수정
- 스타일 수정
- 문서 수정
- 단일 컴포넌트의 소규모 변경
- 기존 DB/API 계약을 변경하지 않는 버그 수정
- 기존 기능에 영향이 제한적인 작업

**필수 제출 항목:**
1. 작업 목적
2. 확인한 파일
3. 변경 예정 파일
4. 기존 기능 영향
5. 테스트 방법
6. 롤백 방법

### B. Architecture Gate

**적용 대상:**
- DB 스키마 변경
- API Endpoint 또는 Request/Response 계약 변경
- 인증 및 권한
- 개인정보 처리
- Agent 구조 또는 자동화 흐름 변경
- 신규 외부 서비스 및 라이브러리 도입
- 배포 또는 환경변수 변경
- 데이터 마이그레이션
- 여러 시스템 영역에 걸친 기능
- 기존 호환성을 깨뜨릴 가능성이 있는 작업

*Architecture Gate는 반드시 사용자 승인 후 구현합니다.*

## 3. 계획서 작성 전 필수 조사

계획서를 작성하기 전에 실제로 다음을 수행해야 합니다.

1. `.agents/AGENTS.md` 읽기
2. `docs/CURRENT_STATUS.md` 읽기
3. `docs/PROJECT_OVERVIEW.md` 읽기
4. `docs/ARCHITECTURE.md` 읽기
5. `docs/DATA_MODEL.md` 읽기
6. `docs/API_CONTRACT.md` 읽기
7. `docs/ADR.md` 읽기
8. `docs/GIT_WORKFLOW.md` 읽기
9. `docs/TODO.md` 읽기
10. 변경 대상 실제 소스코드 읽기
11. `package.json` / `requirements.txt` 등 현재 의존성 확인
12. 현재 브랜치와 main의 차이 확인

계획서에는 반드시 다음을 기록합니다:
- 실제로 읽은 파일
- 현재 코드에서 확인한 사실
- 문서와 코드의 불일치
- 추측 또는 미확인 사항

*실제 코드를 확인하지 않고 기술이나 구조를 가정하지 않습니다.*

## 4. Architecture Gate 필수 제출 항목

Architecture Gate 계획서는 다음 항목을 모두 포함해야 합니다.

### 1. Goal
- 해결하려는 사용자 문제
- 이번 Sprint의 완료 결과

### 2. Current State
- 현재 실제 동작
- 현재 코드 근거
- 현재 제약사항

### 3. Scope
- 이번 작업에서 구현할 것
- 이번 작업에서 구현하지 않을 것

### 4. Existing System Compatibility
- 기존 기술 스택, 라이브러리, 패턴
- 신규 기술 도입 필요 여부 및 중복 기술 발생 여부
*(예: 현재 fetch를 사용하는 프로젝트에 근거 없이 Axios를 추가하는 등 기존 패턴과 중복되는 기술을 도입하지 않는다.)*

### 5. Affected Areas
- Backend / Frontend / Agent / Database / API / Environment Variables / Deployment / Documentation / Tests
*(해당하지 않는 영역도 “영향 없음”이라고 명시한다.)*

### 6. Affected Files
- 수정할 파일, 새로 만들 파일, 삭제할 파일 및 각 파일을 변경하는 이유

### 7. Data Model
- 신규/변경 테이블, 필드, 타입, 필수 여부, 기본값
- UNIQUE/FK/INDEX, 상태값/Enum, 기존 데이터 영향

### 8. Migration Strategy
- 신규 테이블 생성인지 기존 스키마 변경인지 여부
- 데이터 변환 필요 여부, 현재 도구로 가능한지 여부, Alembic 등 정식 Migration 도구 필요 여부
*(create_all을 일반적인 Migration으로 표현하지 않는다.)*

### 9. API Contract
각 API별로 다음을 기록:
- Method, Endpoint, 인증 요구, Request Body, Response Body
- 성공 상태 코드, 실패 상태 코드, 상태 변화, 중복 요청 시 동작

### 10. Security & Privacy
- 인증, 권한, 비밀번호/토큰, 환경변수, PII, 로그 마스킹
- 입력값 검증, Rate Limit, 데이터 접근 범위, 보안상 남는 한계

### 11. Concurrency & Idempotency
- 동시 요청 위험, 중복 생성 위험, 중복 발송 위험
- 트랜잭션 경계, UNIQUE 충돌 처리, 재시도 시 결과
*(해당하지 않으면 “해당 없음”과 이유를 기록한다.)*

### 12. Backward Compatibility
- 기존 CRM, 기존 Agent, 기존 API, 기존 데이터, 기존 배포 환경에 미치는 영향
*(“영향 없음”을 근거 없이 단정하지 않는다.)*

### 13. Environment & Rollout
- 신규 환경변수, 필수/선택 여부, 기본값 허용 여부
- 환경변수 설정 순서, 코드 배포 순서
- Fail-Fast가 기존 서비스에 미치는 영향

### 14. Testing Strategy
자동 테스트와 수동 테스트를 분리합니다.
- **자동 테스트**: 테스트 파일, 프레임워크, 독립 테스트 DB, 성공/실패/경계값, 보안 테스트
- **수동 테스트**: 실제 브라우저, Agent, 외부 애플리케이션, 회귀 테스트
*(운영 DB를 테스트에 사용하지 않는다.)*

### 15. Rollback Plan
- Git revert, 코드 비활성화, DB 처리, 환경변수 처리
- 사용자 데이터 보존, 롤백 후 검증
*(“한 줄 주석 처리”만으로 전체 롤백이라고 표현하지 않는다.)*

### 16. Documentation Updates
수정할 문서를 명시합니다:
- CURRENT_STATUS.md, DATA_MODEL.md, API_CONTRACT.md, ADR.md, CHANGELOG.md, RELEASE.md, TODO.md, 기타 해당 문서

### 17. Git Plan
- 기준 브랜치, 작업 브랜치, 커밋 분리 계획, PR 대상 (main 직접 수정 금지)

### 18. Open Questions
- 사용자 또는 Architect가 결정해야 할 항목만 기록
*(AI가 코드 확인으로 해결할 수 있는 질문을 사용자에게 떠넘기지 않는다.)*

### 19. Definition of Done
- 구현, 테스트, 문서, Git, 회귀 검증, 승인 (체크리스트로 작성)

## 5. Architecture Gate 자체 검증 체크리스트

계획서 제출 전에 AI는 스스로 아래를 검사해야 합니다.

- [ ] 실제 코드 파일을 읽었는가?
- [ ] 기존 문서와 모순되지 않는가?
- [ ] 현재 기술 스택과 중복되는 라이브러리를 추가하지 않았는가?
- [ ] API Request/Response와 상태 코드를 정의했는가?
- [ ] DB 제약조건과 동시성 위험을 검토했는가?
- [ ] 인증·PII·로그 보안을 검토했는가?
- [ ] 신규 환경변수와 배포 순서를 정의했는가?
- [ ] 자동 테스트와 수동 테스트를 나눴는가?
- [ ] 현실적인 Rollback Plan이 있는가?
- [ ] 구현 범위와 제외 범위가 명확한가?
- [ ] 기존 Agent와 CRM 회귀 테스트가 포함되었는가?
- [ ] 현재 구현과 [PLANNED]를 구분했는가?
- [ ] Git 브랜치 및 PR 계획이 있는가?
- [ ] 오픈 퀘스천이 실제로 사용자 결정이 필요한 사항인가?

*하나라도 충족되지 않으면 계획서를 제출하지 말고 먼저 보완합니다.*

## 6. 구현 시작 조건

Architecture Gate 대상 작업은 다음 조건을 모두 충족해야 구현할 수 있습니다.

1. 필수 조사 완료
2. 필수 항목 전체 작성
3. 자체 검증 체크리스트 통과
4. Chief Architect 검토
5. 사용자 승인

*“완벽하다”, “오류가 전혀 없다”, “100% 보장한다”와 같은 검증되지 않은 표현은 사용하지 않습니다. 승인 전에는 기능 코드를 수정하지 않습니다.*

## 7. 계획 변경 관리

구현 중 승인된 계획과 다른 구조가 필요해지면 임의 변경하지 않고 다음 형식으로 변경 요청을 보고합니다.

- 기존 승인 내용
- 새로 발견한 사실
- 변경이 필요한 이유
- 영향 범위
- 대안
- 권장안
- 롤백 영향

Architecture Gate에 영향을 주는 변경은 재승인을 받습니다. 작은 구현 세부사항은 결과 보고에 기록하되, DB/API/보안/Scope 변경은 반드시 재승인합니다.

### Architecture Freeze 원칙
- 한 번 Architecture Gate를 통과하고 승인된 기능의 기본 설계와 아키텍처 결정사항은 해당 Sprint 도중에 임의로 뒤집거나 번복하지 않습니다.
- 확정된 범위를 넘어서는 근본적인 구조 변경은 새로운 Architecture Gate로 분리하여 다음 Sprint에서 다룹니다.
