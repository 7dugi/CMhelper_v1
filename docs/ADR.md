# 기술 의사결정 기록 (Architecture Decision Record)

### 2026-08-06 | Technical Principles 제정
- **주제:** 전사 기술 원칙(Technical Principles) 문서화
- **선택:** `docs/TECHNICAL_PRINCIPLES.md` 신설 및 13대 원칙 제정
- **결정 이유:**
  - AI 협업 시 일관된 아키텍처 원칙(Fail Fast, Thin Client 등)을 준수하게 하여 무분별한 리팩토링이나 외부 라이브러리 도입을 차단함.
  - 모든 설계 및 구현에 기준이 되는 단일 진실 공급원 역할을 수행.

### 2026-08-06 | Authentication: JWT Refresh Token 미도입
- **주제:** JWT 인증 시 Refresh Token 구현 여부
- **선택:** 이번 Sprint에서는 Access Token만 사용 (만료시간 2시간, SessionStorage 보관)
- **배제:** Refresh Token 체계 도입
- **결정 이유:**
  - 복잡한 Refresh 로직 구현보다 B2B 도구에 맞는 핵심 인증 기능 우선 개발
  - Refresh Token 도입은 Sprint B 이후로 연기하여 제품 출시 일정을 단축

### 2026-08-06 | Authentication: Windows Agent 인증 예외 (폐기)
- **주제:** Windows Agent 애플리케이션의 인증 처리
- **선택:** 이번 Sprint에서 Agent는 JWT 인증 대상에서 제외하고 기존 API를 그대로 사용
- **배제:** Agent에 웹과 동일한 JWT Auth 강제 적용
- **결정 이유:**
  - 현재 Agent 구조를 대대적으로 변경하지 않기 위함
- 향후 멀티 회사/멀티 Agent 구조 도입 시 API Key 또는 Device Token 기반으로 안전하게 전환할 예정

### 2026-08-26 | Authentication: Windows PC Agent 메모리 전용 JWT 인증 및 Fail-Closed 체계
- **주제:** JWT 인증이 적용된 메시지 API와 Windows PC Agent 간의 호환성 및 보안
- **선택:**
  - 기존 메시지 API의 인증 예외를 복원하지 않고, Windows PC Agent에 `api_client.py`를 도입하여 `POST /api/auth/login`을 통한 명시적 로그인을 수행.
  - JWT Access Token은 인스턴스/프로세스 메모리에만 보관하고, 비밀번호 입력값은 제출 즉시 위젯에서 삭제.
  - 모든 메시지 대기열 조회, 상태 변경, 취소 요청에 Bearer 토큰을 첨부.
  - 401/403 응답 시 즉시 메모리 토큰을 무효화하고 발송 중단 및 재로그인을 요구 (Fail-Closed).
  - 서버 상태 업데이트(HTTP 200) 응답을 수신한 경우에만 로컬 UI 성공 처리 (가짜 성공 방지 및 서버 권한 보존).
  - `requirements-build.txt` 및 `CMhelper_agent.spec`을 통해 `CMhelper_agent.exe`로의 패키징을 명시적으로 관리.
  - Harness에 `cmhelper_pc_agent_auth` 검증 프로파일을 추가하여 Agent 단위 테스트와 격리 빌드를 검증.
- **배제:** 인증 없는 메시지 API 재개방, Agent 소스·환경변수·로그에 비밀번호 또는 JWT 저장, 이번 작업에서 Device Token 체계 도입
- **결정 이유:** 회사별 데이터 격리와 USER 담당자 범위를 약화하지 않으면서, 별도의 DB 마이그레이션이나 신규 인증 API 없이 현재 Agent의 보안 및 정합성을 확보.
- **상태:** 구현 및 검증 완료 [IMPLEMENTED & VERIFIED]

### 2026-08-06 | Development Gate 도입
- **주제:** Development Gate 도입
- **선택:** Standard Gate + Architecture Gate 이중 절차
- **배제:** 
  - 모든 작업에 동일한 긴 계획서 적용
  - 계획 없이 즉시 구현
- **결정 이유:**
  - 중요 변경의 설계 누락 방지
  - 소규모 작업의 불필요한 절차 방지
  - AI 간 작업 품질 표준화
  - 반복적인 계획 수정 감소
  - 코드와 문서의 정합성 유지

### 2026-08-05 | 자동차 금융 영업 특화 데이터 및 Recipe 기반 플랫폼 확장
- **주제:** CMhelper 장기 제품 방향성 및 플랫폼 확장 아키텍처
- **선택:** CRM + Sales Funnel + Recipe/Template + AI Insight + Customer Portal 구조를 장기 확장 방향으로 정의
- **결정 이유:**
  - 단순 메시지 자동화 도구와 차별화하고, 자동차 금융 영업 과정에서 발생하는 방대한 데이터와 노하우를 축적하기 위함.
  - 개인정보(PII)와 비식별 분석 데이터를 분리 보관함으로써, 향후 AI 기반 영업 지원 및 B2B SaaS 플랫폼 사업으로 안전하게 확장할 수 있는 기반을 마련함.

### 2026-07-16 | 카카오톡 UI 유지보수 전략
- **주제:** 카카오톡 UI 유지보수 전략
- **선택:** Remote Config + Canary Test
- **배제:** 에이전트별 하드코딩
- **결정 이유:**
  - 카카오톡 데스크톱 앱 업데이트 시 전체 고객사에 에이전트를 재배포하는 비용이 매우 크기 때문.
  - 서버 기반 식별자 중앙 관리 방식이 운영 효율성과 장애 대응 속도 측면에서 훨씬 유리함.

### 2026-07-16 | 카카오톡 UI 제어 방식 선정
- **주제:** 카카오톡 데스크톱 앱 자동화 구현 방식
- **선택:** pywinauto (UI 고유 ID 기반 제어)를 기본으로 하고 OpenCV를 폴백으로 사용
- **배제:** PyAutoGUI (맹목적 마우스 좌표 클릭) 단독 사용
- **결정 이유:**
  - 사용자 PC마다 해상도 및 창 크기가 달라 단순 좌표 클릭은 치명적 오류 발생.
  - pywinauto는 윈도우 OS 레벨의 접근으로 가장 안정적인 유지보수성 제공.

### 2026-08-06 | Git Workflow 채택
- **주제:** Git Workflow 채택
- **선택:** Git Flow Lite (main + feature + docs + chore)
- **배제:** 모든 작업을 main에서 직접 수행
- **결정 이유:**
  - 안정성 확보
  - 롤백 용이
  - AI 협업 효율 향상
  - 장기 유지보수 비용 절감
