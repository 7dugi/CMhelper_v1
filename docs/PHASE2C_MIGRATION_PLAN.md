# Phase 2C Migration Plan (Production)

This document outlines the step-by-step procedure to execute the Phase 2C Migration (Contract Foundation and Backfill) on the Production Supabase Database.

**CRITICAL: This migration must NOT be run until explicit GO approval is given by the Chief Architect.**

## Step 1: Production Identity Verification
Run the identity query in Supabase SQL Editor to confirm you are in the correct database.
```sql
SELECT
    current_database() AS database_name,
    current_schema() AS schema_name,
    version() AS postgres_version;
```
*Expected: `postgres`, `public`, `PostgreSQL 17.6`*

## Step 2: Production Precondition SELECT Audit
Run a FAIL-FAST check to ensure no new dirty data has been inserted into Production since Phase 2B.
```sql
SELECT
    (SELECT COUNT(*) FROM customers WHERE company_id IS NULL) AS company_id_is_null,
    (SELECT COUNT(*) FROM customers WHERE assigned_user_id IS NULL) AS assigned_user_id_is_null,
    (SELECT COUNT(*) FROM customers c LEFT JOIN companies co ON c.company_id = co.id WHERE c.company_id IS NOT NULL AND co.id IS NULL) AS invalid_company_fk,
    (SELECT COUNT(*) FROM customers c LEFT JOIN users u ON c.assigned_user_id = u.id WHERE c.assigned_user_id IS NOT NULL AND u.id IS NULL) AS invalid_user_fk,
    (SELECT COUNT(*) FROM customers c JOIN users u ON c.assigned_user_id = u.id WHERE c.company_id != u.company_id) AS cross_tenant_mismatch;
```
*Expected: ALL 0. If any value is > 0, ABORT MIGRATION.*

## Step 3: Contracts Table DDL
Execute the schema creation script to create the `contracts` table.
```sql
CREATE TABLE IF NOT EXISTS contracts (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    assigned_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    
    vehicle_model VARCHAR(255),
    product_type VARCHAR(255),
    capital VARCHAR(255),
    contract_date VARCHAR(255),
    term_months INTEGER,
    expiry_date VARCHAR(255),
    dealer_info VARCHAR(255),
    insurance_active BOOLEAN DEFAULT FALSE,
    supplies_work VARCHAR(255),
    estimate_image VARCHAR(255),
    
    status VARCHAR(50) DEFAULT 'ACTIVE' NOT NULL,
    memo TEXT,
    
    legacy_origin_customer_id INTEGER,
    
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);
```

## Step 4: Indexes / Constraints Verification
Create performance indexes and the idempotency partial unique index.
```sql
CREATE INDEX idx_contracts_company_id ON contracts(company_id);
CREATE INDEX idx_contracts_customer_id ON contracts(customer_id);
CREATE INDEX idx_contracts_assigned_user_id ON contracts(assigned_user_id);
CREATE INDEX idx_contracts_vehicle_model ON contracts(vehicle_model);
CREATE INDEX idx_contracts_expiry_date ON contracts(expiry_date);
CREATE UNIQUE INDEX uq_contracts_legacy_origin ON contracts(legacy_origin_customer_id) WHERE legacy_origin_customer_id IS NOT NULL;
```

## Step 5: Backfill Dry-Run SELECT
Verify exactly which 6 records will be migrated.
```sql
SELECT COUNT(*) FROM customers 
WHERE (contract_car IS NOT NULL AND contract_car != '')
   OR (contract_date IS NOT NULL AND contract_date != '')
   OR (contract_months IS NOT NULL AND contract_months > 0)
   OR (expiry_date IS NOT NULL AND expiry_date != '')
   OR (capital IS NOT NULL AND capital != '')
   OR (product_type IS NOT NULL AND product_type != '');
```
*Expected: 6*

## Step 6: Backfill INSERT
Execute the data backfill.
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

## Step 7: Expected Contract Count Verification
```sql
SELECT COUNT(*) FROM contracts;
```
*Expected: 6*

## Step 8: Customer ↔ Contract Mapping Verification
Run a join query to ensure contracts belong to the correct customer.
```sql
SELECT COUNT(*) FROM contracts con
JOIN customers cus ON con.customer_id = cus.id
WHERE con.legacy_origin_customer_id != cus.id;
```
*Expected: 0*

## Step 9: Tenant Isolation Verification
Run a check to ensure company IDs match perfectly.
```sql
SELECT COUNT(*) FROM contracts con
JOIN customers cus ON con.customer_id = cus.id
WHERE con.company_id != cus.company_id;
```
*Expected: 0*

## Step 10: Expiry / Legacy Data Verification
Validate that data transfer was faithful.
```sql
SELECT COUNT(*) FROM contracts con
JOIN customers cus ON con.customer_id = cus.id
WHERE COALESCE(con.vehicle_model, '') != COALESCE(cus.contract_car, '');
```
*Expected: 0*

## Step 11: API Smoke Test
Deploy the new backend code (including `RESTRICT` models updates) to Production and test endpoints via Postman or Swagger UI.

## Step 12: Frontend Migration Readiness Check
Ensure the Frontend can still read `customers` properly, as we have NOT dropped the legacy fields on the DB or the APIs. Only after the frontend code is migrated to consume `/contracts` will we consider dropping fields (Phase 2D/E).

## Step 13: Rollback / Recovery Procedure
Since this migration is additive (creating a new table and populating it without dropping the original data in `customers`), a rollback is as simple as reverting the backend deployment and keeping the `contracts` table dormant or dropping it entirely:
```sql
DROP TABLE contracts CASCADE;
```
No customer legacy data will be lost during a rollback.
