# Phase 2C Execution Report (Production)

This document records the actual execution results of the Phase 2C Contract Migration on the Production Supabase Database.

## Execution Summary
- **Execution Target:** Supabase Production Database (`postgres`, `public`)
- **Status:** COMPLETED SUCCESSFULLY
- **Initial contracts count:** 0
- **Final contracts count:** 6
- **Expected contracts count:** 6

## Migration Details & Bug Fixes during Execution

The execution encountered two consecutive issues caused by missing `DEFAULT` definitions for NOT NULL columns. The execution failed fast without corrupting data, and the schema was patched accordingly.

### Attempt 1
- **Error:** `null value in column "status" violates not-null constraint`
- **Cause:** `status` had `NOT NULL` but lacked a `DEFAULT` in the actual DB schema definition at execution time.
- **Result:** INSERT failed. `contracts` table remained empty.
- **Resolution:** Added `DEFAULT 'ACTIVE'` to the `status` column.

### Attempt 2
- **Error:** `null value in column "created_at" violates not-null constraint`
- **Cause:** `created_at` (and `updated_at`) had `NOT NULL` but lacked `DEFAULT` expressions.
- **Result:** INSERT failed. `contracts` table remained empty.
- **Resolution:** Added `DEFAULT (now() AT TIME ZONE 'utc')` to `created_at` and `updated_at`. Additionally, identified and patched `insurance_active` to have `DEFAULT FALSE`.

### Attempt 3 (Final Execution)
- **Result:** SUCCESS
- **Backfill Rows Created:** 6

## Backfill Mapping Verification
The migration preserved 1:1 legacy origin relationships exactly as expected for all 6 eligible customers:

| legacy_origin_customer_id | customer_id | vehicle_model | contract_date | term_months | expiry_date |
|---------------------------|-------------|---------------|---------------|-------------|-------------|
| 1                         | 1           | SM3           | 2014-04-01    | 48          | 2018-04-01  |
| 2                         | 2           | 모닝            | 2014-05-26    | 36          | 2017-05-26  |
| 3                         | 3           | 스포티지           | 2014-05-01    | 55          | 2018-12-01  |
| 4                         | 4           | K5 lpg        | 2014-06-01    | 48          | 2018-06-01  |
| 5                         | 5           | 그랜저 LPG        | 2014-06-23    | 48          | 2018-06-23  |
| 6                         | 6           | NULL          | 2023-09-14    | 36          | 2026-09-14  |

**Note on ID Sequence:** The actual generated `contracts.id` values are 3, 4, 5, 6, 7, 8. IDs 1 and 2 were consumed by the sequence generator during the failed Attempt 1 and 2 transactions. This is standard PostgreSQL behavior and no IDs were reassigned.

## Data Consistency Checks
- **Tenant Mismatch Count:** 0
- **Expiry Mismatch Count:** 0
- **Invalid FK Count:** 0
- **Legacy NULL Preservation:** Preserved as NULL (e.g., Customer 6 `vehicle_model`). No artificial values ("Unknown") were injected.

## Schema Idempotency
- **Mechanism:** `CREATE UNIQUE INDEX uq_contracts_legacy_origin ON contracts(legacy_origin_customer_id) WHERE legacy_origin_customer_id IS NOT NULL;`
- **Enforcement:** `ON CONFLICT (legacy_origin_customer_id) DO NOTHING` in the INSERT statement guarantees idempotency.

## Production Foreign Key Status
- `customer_id` -> `customers.id`: `NO ACTION` (Semantically equivalent to `RESTRICT` in immediate evaluation).
- `assigned_user_id` -> `users.id`: `NO ACTION` (Semantically equivalent to `RESTRICT` in immediate evaluation).
- `company_id` -> `companies.id`: `CASCADE`. 
  - *Post-Migration Review Item:* `company_id` cascading delete might violate financial record retention if a company is hard-deleted. A soft-delete lifecycle (ACTIVE/ARCHIVED) for companies should be enforced.

## Rollback Availability
Not required as the migration succeeded. However, since the legacy fields on the `customers` table were left untouched, rolling back simply involves dropping the `contracts` table and returning to the legacy codebase.

## Next Steps (Phase 2D/E)
- Add `company_id`, `customer_id`, `assigned_user_id` indexes to Production DB (missed during DDL).
- Update frontend UI to consume the `/contracts` endpoint.
- Drop legacy contract fields from `customers` once the new API is fully verified in the UI.
