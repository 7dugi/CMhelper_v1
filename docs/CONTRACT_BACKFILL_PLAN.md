# Contract Backfill Plan (Phase 2A)

This document outlines the strategy for migrating existing 1:1 bundled customer contract data into the new `contracts` table (Phase 2).

## 1. Field Mapping

The following mapping defines how legacy `customers` fields map to the new `contracts` table:

- `customers.id` → `contracts.legacy_origin_customer_id` (used for idempotency)
- `customers.company_id` → `contracts.company_id`
- `customers.assigned_user_id` → `contracts.assigned_user_id`
- `customers.contract_car` → `contracts.vehicle_model`
- `customers.product_type` → `contracts.product_type`
- `customers.contract_date` → `contracts.contract_date`
- `customers.contract_months` → `contracts.term_months`
- `customers.expiry_date` → `contracts.expiry_date`
- `customers.capital` → `contracts.capital`
- `customers.dealer_info` → `contracts.dealer_info`
- `customers.supplies_work` → `contracts.supplies_work`
- `customers.insurance_active` → `contracts.insurance_active`
- `customers.estimate_image` → `contracts.estimate_image`

## 2. Backfill Targets

We should only migrate customers that actually have contract data. Creating blank contracts for raw prospects is unnecessary.
**Condition:** A contract will be backfilled only if the customer has at least one of the core vehicle/financial data points.

```sql
WHERE (contract_car IS NOT NULL AND contract_car != '')
   OR (contract_date IS NOT NULL AND contract_date != '')
   OR (contract_months IS NOT NULL AND contract_months > 0)
   OR (expiry_date IS NOT NULL AND expiry_date != '')
   OR (capital IS NOT NULL AND capital != '')
   OR (product_type IS NOT NULL AND product_type != '');
```

## 3. Idempotency

To ensure the migration is idempotent (can be run multiple times safely), we use the `legacy_origin_customer_id` field.
The table schema defines a partial unique index:
```sql
CREATE UNIQUE INDEX uq_contracts_legacy_origin ON contracts(legacy_origin_customer_id) WHERE legacy_origin_customer_id IS NOT NULL;
```
The migration SQL will use `ON CONFLICT (legacy_origin_customer_id) DO NOTHING;`.

## 4. Precondition & Fail Fast

Invalid tenant data should fail migration rather than be silently repaired.
Before executing the backfill, we MUST verify:
1. `company_id` IS NOT NULL
2. `assigned_user_id` IS NOT NULL
3. Valid foreign keys for company and user
4. No cross-tenant mismatch

Any failures here must block the migration. We DO NOT use `COALESCE` to mask missing data.

## 5. Dry-run SQL Queries

Before executing the migration, run these queries in Supabase to estimate the impact.

**Check how many contracts will be created:**
```sql
SELECT COUNT(*)
FROM customers
WHERE (contract_car IS NOT NULL AND contract_car != '')
   OR (contract_date IS NOT NULL AND contract_date != '')
   OR (contract_months IS NOT NULL AND contract_months > 0)
   OR (expiry_date IS NOT NULL AND expiry_date != '')
   OR (capital IS NOT NULL AND capital != '')
   OR (product_type IS NOT NULL AND product_type != '');
```

**Preview the data mapping:**
```sql
SELECT 
    id as legacy_origin_customer_id,
    company_id,
    assigned_user_id,
    contract_car as vehicle_model,
    product_type,
    contract_date,
    contract_months as term_months,
    expiry_date
FROM customers
WHERE (contract_car IS NOT NULL AND contract_car != '')
   OR (contract_date IS NOT NULL AND contract_date != '')
   OR (contract_months IS NOT NULL AND contract_months > 0)
   OR (expiry_date IS NOT NULL AND expiry_date != '')
   OR (capital IS NOT NULL AND capital != '')
   OR (product_type IS NOT NULL AND product_type != '')
ORDER BY id;
```

## 6. Execution Draft SQL

```sql
INSERT INTO contracts (
    company_id,
    customer_id,
    assigned_user_id,
    vehicle_model,
    product_type,
    capital,
    contract_date,
    term_months,
    expiry_date,
    dealer_info,
    insurance_active,
    supplies_work,
    estimate_image,
    legacy_origin_customer_id
)
SELECT 
    c.company_id,
    c.id AS customer_id,
    c.assigned_user_id,
    c.contract_car AS vehicle_model,
    c.product_type,
    c.capital,
    c.contract_date,
    c.contract_months AS term_months,
    c.expiry_date,
    c.dealer_info,
    c.insurance_active,
    c.supplies_work,
    c.estimate_image,
    c.id AS legacy_origin_customer_id
FROM customers c
WHERE ((c.contract_car IS NOT NULL AND c.contract_car != '')
   OR (c.contract_date IS NOT NULL AND c.contract_date != '')
   OR (c.contract_months IS NOT NULL AND c.contract_months > 0)
   OR (c.expiry_date IS NOT NULL AND c.expiry_date != '')
   OR (c.capital IS NOT NULL AND c.capital != '')
   OR (c.product_type IS NOT NULL AND c.product_type != ''))
ON CONFLICT (legacy_origin_customer_id) DO NOTHING;
```

## 6. Rollback Strategy

The transition to Phase 2 is an **Additive Migration**.
1. We create the `contracts` table.
2. We run the backfill (populating `contracts` from `customers`).
3. We switch the application to read from `contracts` instead of `customers` fields.
4. We monitor for stability.

**If issues occur during Phase 2B/2C (Read Switch):**
We simply revert the application code to read the legacy fields on `customers`. Because we did not `DROP` or `ALTER` the legacy fields, the system will instantly revert to 1:1 behavior without data loss.

Only after prolonged stability (Phase 2D/E) will we write a cleanup script to drop the legacy fields from `customers`.
