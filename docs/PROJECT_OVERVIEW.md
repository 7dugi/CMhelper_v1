# 프로젝트 개요 (CMhelper)

## 1. 프로젝트 목표 및 Grand Vision
CMhelper는 단순한 "카카오톡 자동 발송 프로그램"을 넘어, 장기렌트/리스/할부 등 자동차 금융 영업의 모든 프로세스를 관통하는 **자동차 영업 특화 B2B SaaS 플랫폼**을 목표로 합니다. 

### 향후 확장 가능한 핵심 도메인 (Platform Vision)
1. **CRM**: 고객 데이터 통합 및 세그멘테이션 관리.
2. **멀티채널 자동화**: 카카오톡 중심의 메신저 마케팅 및 자동화 발송.
3. **영업 퍼널 분석**: LEAD 단계부터 CONTRACT까지의 전환율 및 이탈 사유(Loss Reason) 분석.
4. **영업 Recipe / Template**: 업종, 차종, 고객군별 Best Practice 콘텐츠 라이브러리 제공.
5. **AI 상담 인사이트**: 비식별 데이터를 기반으로 고객 성향 분석 및 최적 상품 추천.
6. **차량 재고 / 상품 추천**: 금융사 및 제조사 데이터 기반 실시간 재고 탐색 및 매칭.
7. **고객용 Contract Portal**: 고객이 직접 잔존가치, 만기일, 차량 반납/인수 시뮬레이션을 확인할 수 있는 고객 전용 웹페이지.

---

## 2. 개발 로드맵 및 우선순위

*   **P0: CRM + 카카오 발송 안정화** (통합 고객 관리 및 카카오톡 1:1 맞춤형 발송, 수동 기반 예약 발송 처리)
*   **P1: 발송 이력 + 운영 안정성 고도화** 
    - 카나리아 테스트 연동 및 Remote Config 도입
    - 발송 상태 UI 직관화 및 Agent 자동 업데이트
    - *(현재 범위 제외: Background Agent, Windows Service 도입, PC 자동 시작 및 무인 완전 자동 예약 발송)*
*   **P2: Sales Funnel + Stage History + Loss Reason** (영업 단계 트래킹 및 전환율/이탈 분석)
*   **P3: Recipe / Template** (업종/차종/고객군별 Best Practice 콘텐츠 제공)
*   **P4: Inventory / Product** (금융사 및 제조사 실시간 재고/상품 조건 매핑)
*   **P5: AI Insight** (인바운드 고객 상담 분석 및 최적 상품 조건 추천)
*   **P6: Customer Portal** (고객 직접 접속용 계약 관리 및 시뮬레이션 웹페이지)
*   **P7: 금융사/OEM용 Aggregated Analytics** (제조사/금융사용 비식별 집계 통계)

---

## 3. 프로젝트 관리 및 운영 원칙

*   **중요 기능은 `docs/DEVELOPMENT_GATE.md`의 Architecture Gate를 통과한 후 개발합니다.**
*   **Git Workflow 공식 운영 정책**: Git Flow Lite (`main`, `feature`, `docs`, `chore` 브랜치 분리 운용)
    - 상세 정책은 [GIT_WORKFLOW.md](./GIT_WORKFLOW.md)를 참조하십시오.
    - AI 협업 시에도 본 정책을 반드시 준수해야 합니다.
