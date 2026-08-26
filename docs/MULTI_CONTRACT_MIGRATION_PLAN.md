# Contract Data Migration Plan

## 1. 개요 및 목적
- **목적:** Phase 2C 마이그레이션 이후 신규 등록되어 `customers` 테이블의 legacy 필드에만 계약 정보가 존재하고 `contracts` 테이블에는 생성되지 않은(최봉덕 ID 10 등) 고객들의 계약 데이터를 `contracts` 테이블로 백필(Backfill)합니다.
- **Source of Truth 원칙:** 계약 정보의 authoritative write target 및 Source of Truth는 전적으로 `contracts` 테이블입니다. `customers`의 legacy 필드는 Phase 2E 안정화 전까지 Rollback/Read-only 용도로만 유지됩니다.
- **Idempotency (멱등성):** `legacy_origin_customer_id`를 기준으로 이미 마이그레이션된 데이터는 제외하도록 설계되어 반복 실행해도 중복 생성되지 않습니다.
- **Rollback 전략:** 
  - 기본 Rollback: Application read path를 다시 legacy customer fields로 되돌리는 Logical Rollback을 수행합니다.
  - DB row 삭제: 오직 이번 migration 직후 심각한 오류가 확인되고 별도 승인된 maintenance rollback에서만 예외적으로 허용됩니다. (계약 이력 Hard Delete 금지 정책 준수)

## 2. 마이그레이션 대상 조건 (Eligibility Rule)
Phase 2C와 동일하게 다음 중 하나라도 유의미한 계약 데이터가 존재하는 고객을 대상으로 합니다.
- `contract_car`, `contract_date`, `contract_months`, `expiry_date`, `capital`, `product_type` 중 하나라도 존재하는 경우

## 3. Production DB 마이그레이션 쿼리

### Step 1: SELECT Dry-run (마이그레이션 대상 사전 검증)
> [!IMPORTANT]
> 반드시 아래 쿼리를 먼저 실행하여 예상 대상 Row 수와 실제 데이터를 확인하세요. 특히 최봉덕(ID 10) 고객이 포함되어 있는지 확인해야 합니다.

```sql
SELECT 
    c.id AS customer_id,
    c.name,
    c.company_id,
    c.assigned_user_id,
    c.contract_car AS legacy_vehicle,
    c.contract_date AS legacy_contract_date,
    c.contract_months AS legacy_term,
    c.expiry_date AS legacy_expiry,
    (SELECT COUNT(*) FROM contracts ct WHERE ct.customer_id = c.id) AS current_contracts_count,
    CASE WHEN EXISTS (SELECT 1 FROM contracts ct WHERE ct.legacy_origin_customer_id = c.id) THEN 'Y' ELSE 'N' END AS is_mapped
FROM customers c
WHERE (
      (c.contract_car IS NOT NULL AND c.contract_car != '') OR
      (c.contract_date IS NOT NULL AND c.contract_date != '') OR
      (c.contract_months IS NOT NULL AND c.contract_months > 0) OR
      (c.expiry_date IS NOT NULL AND c.expiry_date != '') OR
      (c.capital IS NOT NULL AND c.capital != '') OR
      (c.product_type IS NOT NULL AND c.product_type != '')
  )
  AND NOT EXISTS (
      SELECT 1 FROM contracts ct WHERE ct.legacy_origin_customer_id = c.id
  );
```
**[기대 결과 - 최봉덕 ID 10]**
- `legacy_vehicle`: 아반떼, `legacy_contract_date`: 2022-03-01
- `current_contracts_count`: 1 (Contract ID 9가 이미 존재하므로)
- `is_mapped`: 'N' (기존 Contract ID 9는 신규 추가된 건으로 `legacy_origin_customer_id`가 NULL임)

### Step 2: 마이그레이션 실행 (INSERT SQL)
> [!WARNING]
> 기존 Contract ID 9 등 이미 존재하는 Contract는 절대 수정하거나 삭제하지 않고 신규 독립 row로 추가됩니다.

```sql
INSERT INTO contracts (
    company_id,
    customer_id,
    assigned_user_id,
    legacy_origin_customer_id,
    vehicle_model,
    contract_date,
    term_months,
    expiry_date,
    capital,
    product_type,
    supplies_work,
    insurance_active,
    dealer_info,
    status,
    created_at,
    updated_at
)
SELECT 
    c.company_id,
    c.id AS customer_id,
    c.assigned_user_id,
    c.id AS legacy_origin_customer_id,
    c.contract_car AS vehicle_model,
    c.contract_date,
    c.contract_months AS term_months,
    c.expiry_date,
    c.capital,
    c.product_type,
    c.supplies_work,
    c.insurance_active,
    c.dealer_info,
    'ACTIVE' AS status,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM customers c
WHERE (
      (c.contract_car IS NOT NULL AND c.contract_car != '') OR
      (c.contract_date IS NOT NULL AND c.contract_date != '') OR
      (c.contract_months IS NOT NULL AND c.contract_months > 0) OR
      (c.expiry_date IS NOT NULL AND c.expiry_date != '') OR
      (c.capital IS NOT NULL AND c.capital != '') OR
      (c.product_type IS NOT NULL AND c.product_type != '')
  )
  AND NOT EXISTS (
      SELECT 1 FROM contracts ct WHERE ct.legacy_origin_customer_id = c.id
  );
```

### Step 3: Post Verification SQL (실행 후 검증)
```sql
SELECT c.id AS customer_id, c.name, 
       (SELECT COUNT(*) FROM contracts ct WHERE ct.customer_id = c.id) AS final_contract_count
FROM customers c
WHERE c.id = 10; -- 최봉덕 고객 확인
```
**[기대 결과 - 최봉덕 ID 10]**
- `final_contract_count`: **2** (기존 2022-03-02 계약 + 새로 마이그레이션된 2022-03-01 계약)
