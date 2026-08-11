# Phase 2B Production Data Audit

이 문서는 Phase 2A에서 설계된 Contract 마이그레이션 전략이 운영(Production) 데이터에 적용될 경우의 영향을 분석하기 위한 최종 검증 결과입니다.

**[주의]** 기존에 보고되었던 수치(company_id NULL, Customer ID 10 이슈 등)는 Production Supabase가 아닌 **Local SQLite Dry-run Result** 였으며 더 이상 유효하지 않습니다. 아래 결과가 공식(Authoritative) Production 데이터입니다.

## 1. DB Identity
- current_database = postgres
- current_schema = public
- PostgreSQL version = 17.6

## 2. Supabase Production Audit Result

### A. Data Overview
- PRODUCTION_TOTAL_CUSTOMERS: 8
- PRODUCTION_BACKFILL_ELIGIBLE_CUSTOMERS: 6
- PRODUCTION_NO_CONTRACT_DATA_CUSTOMERS: 2
- PRODUCTION_EXPECTED_INITIAL_CONTRACTS: 6

### B. Tenant / Ownership Mapping Audit
- 존재하지 않는 `company_id` 참조 (NULL 포함): 0
- 존재하지 않는 `assigned_user_id` 참조: 0
- Cross-tenant reference (고객과 담당자의 회사 불일치): 0

### C. Data Quality Audit (Anomalies)
- 계약 차량(`contract_car`)은 있는데 계약일(`contract_date`)이 없는 고객: 0
- 계약일(`contract_date`)은 있는데 차량 정보(`contract_car`)가 없는 고객: 1
- `date_greater_than_expiry`: 0
- 기타(음수 개월수 등): 0

차량 정보가 없지만 의미 있는 계약 데이터(계약일, 계약 개월, 만기일 등)가 존재하는 케이스가 발견되었으나, 백필 정책에 따라 Contract 생성 대상에 포함되며 임의의 문자열로 변환(보정)하지 않습니다.

### D. Expiry Logic Re-Verify
- `contract_date` + `contract_months`와 저장된 `expiry_date`의 불일치 건수: 0

## 3. Policy Decisions Based on Audit

### A. Fail-Fast Migration (No COALESCE)
Production에서 Tenant Isolation 데이터(`company_id`, `assigned_user_id`)의 무결성이 확인되었으므로, 잘못된 데이터를 조용히 복구하는 `COALESCE` 로직은 마이그레이션에서 제거되었습니다. 향후 마이그레이션 시 잘못된 외래키나 Tenant 맵핑 데이터가 유입되면 전체 마이그레이션이 실패(Fail-Fast)하도록 설계됩니다.

### B. Contract Retention
계약 정보는 과거 금융 기록이므로 삭제 정책을 매우 보수적으로 가져갑니다.
- `Contract.customer_id`: ON DELETE RESTRICT (Customer hard delete 방지)
- `Contract.assigned_user_id`: ON DELETE RESTRICT (User hard delete 방지)
- `Contract.company_id`: ON DELETE CASCADE (Tenant 삭제 시 모든 데이터 파기)

## 4. Migration GO / NO-GO Criteria
### 판정: **PHASE 2C READY**

Phase 2C Production 마이그레이션 및 Contract 백필 실행을 위한 준비가 완료되었습니다. 데이터 무결성이 증명되었고, Migration SQL 및 Idempotency 검증 로직이 확정되었습니다.
