# Customer Contract Field Audit

## 1. Field Classification

현재 `Customer` 모델의 모든 필드를 분석하여 다음과 같이 분류했습니다.

### A. Customer-level (고객 기본 정보)
- `name` (고객명)
- `contact` (연락처)
- `region` (지역)
- `company` (직장명)
- `anniversary` (기념일/생일)
- `memo` (고객 일반 메모)
- `is_prospect` (가망 고객 여부 - 고객 단위 상태)
- `is_contracted` (계약 고객 여부 - 향후 Contracts 유무로 대체 가능하지만 현재는 고객 상태 플래그)
- `extra` (사용자 정의 추가 필드 - 고객 단위)

### B. Contract-level (계약 관련 정보 - 분리 대상)
- `contract_car` (계약 차량) -> `Contract.vehicle_model`
- `contract_date` (계약일) -> `Contract.contract_date`
- `contract_months` (계약 기간) -> `Contract.term_months`
- `months` (계약 기간 레거시) -> `Contract.term_months`
- `expiry_date` (만기일 - 계산됨) -> `Contract.expiry_date`
- `capital` (금융사) -> `Contract.capital`
- `product_type` (상품 종류 - 렌트/리스 등) -> `Contract.product_type`
- `supplies_work` (용품 작업 내역) -> `Contract.supplies_work`
- `insurance_active` (보험 가입 여부) -> `Contract.insurance_active`
- `dealer_info` (딜러 정보) -> `Contract.dealer_info`
- `estimate_image` (견적서 이미지) -> `Contract.estimate_image`

### C. Consultation / Activity-level (상담 및 활동)
- `sent_quotes` (전송된 견적서 이력) -> 향후 `Consultation` 또는 별도의 Activity 엔티티로 이동 검토 필요. (현재는 Contract 종속보다는 고객-영업 히스토리에 가깝습니다.)

### D. Needs Review (추가 검토 필요)
- `sent_quotes`: 견적서를 특정 계약에 종속시킬지, 고객의 독립적인 상담 이력으로 남길지 결정 필요. (현재 Phase 2에서는 Customer 모델에 유지)

## 2. Customer -> Contract Field Mapping Table

현재 데이터에서 신규 `contracts` 테이블로 마이그레이션할 때 적용할 매핑 룰입니다.

| Current Customer Field | Future Entity | Future Contract Field | Migration Rule | Nullable? | Transformation Required? | Notes |
|---|---|---|---|---|---|---|
| `contract_car` | Contract | `vehicle_model` | existing value copy | YES | NO | |
| `contract_date` | Contract | `contract_date` | existing value copy | YES | NO | |
| `contract_months` | Contract | `term_months` | existing value copy | YES | NO | `months` 필드와 통합 필요성 검토 |
| `expiry_date` | Contract | `expiry_date` | existing value copy | YES | YES (Recalculate) | 백엔드에서 자동 계산되나 기존 값 유지 보장 필요 |
| `capital` | Contract | `capital` | existing value copy | YES | NO | |
| `product_type` | Contract | `product_type` | existing value copy | YES | NO | |
| `supplies_work` | Contract | `supplies_work` | existing value copy | YES | NO | |
| `insurance_active`| Contract | `insurance_active` | existing value copy | NO (default: False)| NO | |
| `dealer_info` | Contract | `dealer_info` | existing value copy | YES | NO | |
| `estimate_image` | Contract | `estimate_image` | existing value copy | YES | NO | |
| `id` | Contract | `legacy_origin_customer_id`| existing value copy | YES | NO | Idempotent migration을 위한 식별키 |

## 3. Delete / Data Retention Safety Audit
- **Customer 삭제 시**: `Contract.customer_id`의 외래키에 `ondelete="CASCADE"`가 설정되어 있지 않습니다(의도된 설계). 고객 기록이 지워지더라도 금융/계약 기록은 함부로 삭제되지 않도록 보존해야 합니다. 따라서 애플리케이션 레벨에서 명시적인 삭제나 상태 변경(`INACTIVE`)을 거쳐야 합니다.
- **User 삭제 시**: `assigned_user_id` 또한 CASCADE되지 않으므로, 퇴사자의 계약 기록이 고아(orphan) 객체가 되지 않고 다른 관리자에게 이관될 수 있는 구조입니다.
- **결론**: 안전하게 보호되고 있으며 현재의 Retention 정책을 충족합니다.
