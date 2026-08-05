# CMhelper 데이터 모델 및 확장성 검토 (Data Model & Future Extension)

이 문서는 현재 구현된 데이터베이스 구조와, CMhelper를 "자동차 금융 영업 특화 B2B SaaS"로 확장하기 위해 향후 고려해야 할 도메인 모델을 정의합니다. 

현재 시스템과 미래 기획 간의 혼동을 막기 위해 상태 태그(`[IMPLEMENTED]`, `[PLANNED]`, `[PROPOSED]`)를 엄격히 적용합니다.

---

## 1. 현재 구현된 데이터 모델 `[IMPLEMENTED]`

현재 FastAPI + SQLAlchemy (SQLite) 기반으로 다음 테이블들이 실제 운영되고 있습니다.

### 1.1 Customer (`customers`)
고객의 기본 정보 및 계약 정보를 담고 있으며, 동적 필드 저장을 위해 `extra` (JSON) 컬럼을 지원합니다.
- **주요 필드:** `id`, `name`, `contact`, `company`, `contract_car`, `product_type`, `is_prospect`, `is_contracted`, `extra`
- **관계:** `Consultation`, `MessageTask`와 1:N 관계. 
- **[KNOWN ISSUE] 마이그레이션 리스크:** 현재 리드(Lead), 가망(Prospect), 계약(Contract) 고객 정보가 하나의 테이블에 혼재되어 있습니다. 향후 `Opportunity` 및 `Contract` 분리 정규화 시 마이그레이션 전략이 필요합니다.

### 1.2 Consultation (`consultations`)
고객과의 단순 상담 이력 및 노트를 기록합니다.
- **주요 필드:** `id`, `customer_id`, `notes`, `created_at`

### 1.3 MessageTask (`message_tasks`)
에이전트가 처리할 발송 대기열 및 로그 데이터를 관리합니다. 엔터프라이즈 장애 복구(`V4.1`) 구조가 반영되어 있습니다.
- **주요 필드:** `id`, `customer_id`, `message_text`, `status` (`RESERVED`, `PROCESSING`, `SUCCESS`, `FAILED`, `RECOVERY`, `CANCELLED`), `scheduled_at`
- **트래킹 필드:** `locked_by`, `locked_at`, `heartbeat_at`, `retry_count`, `error_code`

### 1.4 FieldDefinition (`field_definitions`)
고객 정보의 커스텀 필드(메타데이터)를 정의합니다.

---

## 2. 향후 확장 데이터 모델 `[PLANNED]` / `[PROPOSED]`

CMhelper를 "영업 데이터 축적 및 분석 플랫폼"으로 발전시키기 위해 다음과 같은 구조적 분리 및 확장을 제안합니다.

### 2.1 영업 퍼널(Sales Funnel) 관리 모델 `[PLANNED]`
- **`Opportunity`**: 리드 획득부터 계약까지의 단계를 트래킹.
  - 필드 예시: `id`, `customer_id`, `stage` (LEAD, CONSULTATION, QUOTE, CREDIT_REVIEW, APPROVED, CONTRACT), `outcome`, `loss_reason_id`
- **`SalesStageHistory`**: 각 단계 진입/종료 시점 및 체류 시간.
- **`LossReason`**: 이탈 사유 마스터 테이블.

### 2.2 자동차 금융 영업 특화 템플릿 & Recipe 모델 `[PLANNED]`
- **`Template` / `Recipe`**: 마스터 콘텐츠 및 상담 베스트 프랙티스 로직.
- **`OpportunityRecipeHistory` (N:M 매핑)**: 단일 Opportunity에서 여러 레시피/템플릿을 사용해 본 이력을 추적하여 A/B 테스트 및 AI 학습 데이터로 활용하는 매핑 테이블.

### 2.3 AI 상담 및 인사이트 모델 `[PROPOSED]`
개인정보와 분석 데이터를 논리적으로 분리(Decoupling)하여 저장합니다.
- **`ConsultationInsight`**: PII(개인정보) 원문이 아닌, AI가 추출한 비식별 메타데이터만 저장 (`customer_type`, `key_decision_factor` 등).

### 2.4 고객용 계약 관리 (Customer Portal) 모델 `[PROPOSED]`
- **`Contract`**: 기존 `customers`의 계약 정보를 독립 테이블로 정규화합니다.
  - **관계:** `Opportunity` 1 : N `Contract` (하나의 영업 건에서 다중 견적 및 재계약/계약 변경 대응).

### 2.5 재고 및 상품 데이터 모델 `[PROPOSED]`
- **`Vehicle` / `Product` / `Inventory`**: 제조사 및 금융사 표준 제원 및 실시간 재고 정보.

---

## 3. 핵심 아키텍처 관계 요약 (Target ERD 방향성)

1. `Customer` ──(1:N)── `Opportunity` ──(1:N)── `Contract`
2. `Opportunity` ──(1:N)── `SalesStageHistory`
3. `Opportunity` ──(N:M via `OpportunityRecipeHistory`)── `Recipe` / `Template`
4. `Contract` ──(N:1)── `Vehicle` & `Product`
