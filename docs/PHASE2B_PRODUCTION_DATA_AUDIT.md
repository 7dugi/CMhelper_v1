# Phase 2B Production Data Audit

이 문서는 Phase 2A에서 설계된 Contract 마이그레이션 전략이 운영(Production) 데이터에 적용될 경우의 영향을 분석하기 위해, READ-ONLY 쿼리만을 수행하여 산출한 감사 결과입니다. 

## 1. Production Data Overview
- **전체 Customer 수**: 10
- **계약 관련 데이터가 하나라도 존재하는 Customer 수 (Backfill 대상)**: 8
- **계약 관련 데이터가 전혀 없는 Customer 수**: 2
- **마이그레이션 후 예상 생성 Contract 수**: 8

### 필드별 데이터 존재 수
- `contract_car`: 3건
- `contract_date`: 7건
- `contract_months`: 7건
- `expiry_date`: 7건
- `capital`: 1건
- `product_type`: 5건
- `supplies_work`: 1건
- `insurance_active`: 1건 (True) / 9건 (False)
- `dealer_info`, `estimate_image`: 0건

## 2. Production Data Quality Audit (Anomalies)
데이터 정합성을 해치는 다음과 같은 예외 데이터가 발견되었습니다. (절대 자동 수정하지 않으며, Backfill 스크립트는 이 형태 그대로 Contract 테이블에 이관합니다)

1. **계약 차량(`contract_car`)은 있는데 계약일(`contract_date`)이 없는 고객**: 1건
   - **조치 권장**: 마이그레이션 후 영업 담당자가 수동으로 계약일을 업데이트해야 합니다.
2. **계약일(`contract_date`)은 있는데 차량 정보(`contract_car`)가 없는 고객**: 5건
   - **조치 권장**: 차량 정보는 향후 필수 입력이 권장되나, 현재 데이터는 차량 정보 `NULL`인 상태로 마이그레이션 됩니다.
3. **만기일(`expiry_date`) 계산 로직 검증**:
   - 기존의 `expiry_date`는 백엔드 `_compute_expiry()` 함수를 통해 "계약일 + 계약기간(개월)"으로 자동 계산되고 있었습니다.
   - 데이터 불일치(`contract_date > expiry_date`, `contract_date` 없음 등) 오류는 백엔드 계산 로직 덕분에 DB 상에서 발견되지 않았습니다 (0건).

## 3. Backfill Eligibility Rule
다음 필드 중 하나라도 값이 존재(NULL 또는 빈 문자열이 아님)할 경우, 해당 고객은 "계약 데이터 보유 고객"으로 간주하여 `Contract` Row를 1건 생성합니다.
- `contract_car`, `contract_date`, `contract_months`, `expiry_date`, `capital`, `product_type`

**결과:** 총 10명의 고객 중 **8명**이 이 조건에 부합하여, 마이그레이션 시 **8건의 Contract**가 생성될 예정입니다.

## 4. Tenant / Ownership Mapping Audit
**주의(Blocking Issue 유무 판단):**
- **존재하지 않는 `company_id` 참조 (NULL 포함)**: 1건 (Customer ID: 10, `company_id` IS NULL)
- **존재하지 않는 `assigned_user_id` 참조**: 0건
- **Cross-tenant reference (고객의 회사와 담당자의 회사가 다름)**: 0건

**[중요] NULL `company_id` 이슈**: 
Customer ID 10번 고객의 `company_id`가 NULL 상태입니다. 향후 `contracts` 테이블은 `company_id`를 NOT NULL로 강제하므로 (`nullable=False`), 이 데이터가 그대로 마이그레이션 될 경우 **DB 제약 조건 위반 에러**가 발생합니다. Phase 2C 이전에 해당 고객의 `company_id`를 기본 Company로 맵핑(Backfill)하거나 제외하는 스크립트 수정이 필수적입니다.

## 5. Expiry Date & Dashboard Statistics Logic
- 기존 대시보드 통계는 `Customer` 엔티티를 기준으로 '만기 1개월 전', '만기 3개월 전' 등을 계산하고 있었습니다. 
- 향후 이 로직은 `Contract` 엔티티 기준으로 전환되어야 합니다. 한 고객이 여러 차량(Contract)을 가지게 되면, 각각의 Contract마다 독립적인 만기 통계(알림)가 작동해야 하기 때문입니다. 이번 Phase 2B/2C에서는 UI/대시보드를 변경하지 않으며, 향후 API 수정 시 반영됩니다.

## 6. Migration GO / NO-GO Criteria
### 판정: **PHASE 2C NO-GO (조건부 승인 필요)**

**NO-GO 사유:**
- `company_id`가 NULL인 Customer가 존재(1건)하여, 현재의 `contracts` NOT NULL 스키마로 INSERT 시 오류(Exception) 발생이 확정적입니다.

**해결 방안 및 GO 전환 조건:**
- Backfill SQL 스크립트 내에 `company_id`가 NULL인 경우, `assigned_user_id`의 `company_id`를 참조하거나 시스템 디폴트 Company ID를 할당하도록 쿼리 수정 (예: `COALESCE(c.company_id, u.company_id)`). 
- 위 방안을 Backfill Plan(`CONTRACT_BACKFILL_PLAN.md`)에 명시하고 사용자(User)의 승인을 득한 후 Phase 2C로 진입합니다.
