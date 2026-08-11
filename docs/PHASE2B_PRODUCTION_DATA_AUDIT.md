# Phase 2B Production Data Audit

이 문서는 Phase 2A에서 설계된 Contract 마이그레이션 전략이 운영(Production) 데이터에 적용될 경우의 영향을 분석하기 위한 감사 결과입니다.

**[주의]** 기존에 보고되었던 수치는 Production Supabase가 아닌 **Local SQLite Dry-run Result** 였습니다.
실제 Production Supabase 데이터에 대한 조회가 필요하며, `docs/sql/phase2b_production_audit_queries.sql` 스크립트를 통해 Supabase SQL Editor에서 수동으로 추출 후 아래의 Supabase 결과란을 업데이트해야 합니다.

## 1. Local SQLite Dry-run Result (참고용)

### Data Overview
- **전체 Customer 수**: 10
- **계약 관련 데이터가 하나라도 존재하는 Customer 수 (Backfill 대상)**: 8
- **계약 관련 데이터가 전혀 없는 Customer 수**: 2
- **마이그레이션 후 예상 생성 Contract 수**: 8

### Data Quality Audit (Anomalies)
- **계약 차량(`contract_car`)은 있는데 계약일(`contract_date`)이 없는 고객**: 1건
- **계약일(`contract_date`)은 있는데 차량 정보(`contract_car`)가 없는 고객**: 5건
- **NULL company_id 이슈**: Customer ID 10번 고객의 `company_id`가 NULL 상태임 확인.

## 2. Supabase Production Read-only Result (PENDING)

**[진행 상태: PENDING - 사용자의 쿼리 실행 결과 대기 중]**

### A. Data Overview
- PRODUCTION_TOTAL_CUSTOMERS: [TBD]
- PRODUCTION_BACKFILL_ELIGIBLE_CUSTOMERS: [TBD]
- PRODUCTION_NO_CONTRACT_DATA_CUSTOMERS: [TBD]
- PRODUCTION_EXPECTED_INITIAL_CONTRACTS: [TBD]

### B. Tenant / Ownership Mapping Audit
- 존재하지 않는 `company_id` 참조 (NULL 포함): [TBD]
- 존재하지 않는 `assigned_user_id` 참조: [TBD]
- Cross-tenant reference (고객과 담당자의 회사 불일치): [TBD]

### C. Expiry Logic Re-Verify
- `contract_date` + `contract_months`와 저장된 `expiry_date`의 불일치 건수: [TBD]

## 3. Migration GO / NO-GO Criteria
### 판정: **PHASE 2C NO-GO (조건부 승인 및 실데이터 검증 전까지 대기)**

**NO-GO 사유:**
- Local DB에서 `company_id` NULL 케이스가 발견되어 SQL 상에 `COALESCE` 안전장치를 반영하였으나, Production에서도 동일한 문제가 얼마나(그리고 왜) 존재하는지 확인해야 합니다.
- 실제 Production 데이터의 쿼리 결과(Anomaly count, Eligibility 등)를 확인하기 전까지는 어떠한 DDL도 실행할 수 없습니다.
