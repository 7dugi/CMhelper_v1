# Phase 3A Opportunity Migration Plan

## 1. DDL Migration (CREATE TABLE)
The `opportunities` table must be created with necessary foreign keys and indexes.

```sql
CREATE TABLE opportunities (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    assigned_user_id INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    purpose VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'NEW',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_opportunities_company_id FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE,
    CONSTRAINT fk_opportunities_customer_id FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE RESTRICT,
    CONSTRAINT fk_opportunities_user_id FOREIGN KEY (assigned_user_id) REFERENCES users (id) ON DELETE RESTRICT
);
```

## 2. Indexes
Composite indexes are recommended based on query patterns.

```sql
CREATE INDEX ix_opportunities_company_id_status ON opportunities (company_id, status);
CREATE INDEX ix_opportunities_assigned_user_id ON opportunities (assigned_user_id);
CREATE INDEX ix_opportunities_customer_id ON opportunities (customer_id);
```

## 3. Post Verification
```sql
SELECT count(*) FROM opportunities;
-- Expected: 0
```

## 4. Rollback Plan
If there is a severe schema error right after creation and row count is 0:
```sql
DROP TABLE IF EXISTS opportunities;
```
If data has already been accumulated, DO NOT DROP the table. Use Application-level logical rollback by disabling Opportunity features in the UI.

## 5. Production Status

PHASE 3A PRODUCTION MIGRATION = COMPLETE

- Production migration completed
- Schema verified
- FK verified
- Delete Rules verified
- Index verified
- Initial row count = 0
- Backfill not required
- Phase 3A production status = COMPLETE

