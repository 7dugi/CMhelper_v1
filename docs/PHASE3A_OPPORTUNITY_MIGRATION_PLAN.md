# Phase 3A Opportunity Migration Plan

## 1. DDL Migration (CREATE TABLE)
The `opportunities` table must be created with necessary foreign keys and indexes.

```sql
CREATE TYPE opportunity_status AS ENUM ('NEW', 'QUOTING', 'NEGOTIATING', 'WON', 'LOST', 'ON_HOLD');

CREATE TABLE opportunities (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    assigned_user_id INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    purpose VARCHAR,
    status opportunity_status NOT NULL DEFAULT 'NEW',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_opportunities_company_id FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE,
    CONSTRAINT fk_opportunities_customer_id FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE RESTRICT,
    CONSTRAINT fk_opportunities_user_id FOREIGN KEY (assigned_user_id) REFERENCES users (id) ON DELETE RESTRICT
);
```
*(Note: In Phase 3A, SQLAlchemy's `ondelete` configurations might map differently depending on the schema, but standard FK restrictions apply. The actual migration will use Alembic if set up, or raw Supabase SQL).*

## 2. Indexes
```sql
CREATE INDEX ix_opportunities_company_id ON opportunities (company_id);
CREATE INDEX ix_opportunities_customer_id ON opportunities (customer_id);
CREATE INDEX ix_opportunities_assigned_user_id ON opportunities (assigned_user_id);
CREATE INDEX ix_opportunities_status ON opportunities (status);
```

## 3. Post Verification
```sql
SELECT count(*) FROM opportunities;
```

## 4. Rollback Plan
```sql
DROP TABLE IF EXISTS opportunities;
DROP TYPE IF EXISTS opportunity_status;
```
