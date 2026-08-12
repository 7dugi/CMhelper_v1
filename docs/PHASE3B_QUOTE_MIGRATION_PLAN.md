# Phase 3B: Quote Migration Plan

## Overview
This document outlines the migration plan to introduce the `quotes` table into the production database. The `Quote` entity is part of the Phase 3 Architecture to separate the financial calculation snapshots from the underlying `Opportunity`.

## Target Schema (`quotes`)

| Column Name        | Type              | Constraints                                                | Description                          |
|--------------------|-------------------|------------------------------------------------------------|--------------------------------------|
| `id`               | SERIAL            | PRIMARY KEY                                                | Auto-incrementing primary key        |
| `company_id`       | INTEGER           | NOT NULL, FK(`companies.id`) ON DELETE CASCADE             | Tenant isolation identifier          |
| `opportunity_id`   | INTEGER           | NOT NULL, FK(`opportunities.id`) ON DELETE RESTRICT        | Parent opportunity identifier        |
| `assigned_user_id` | INTEGER           | NOT NULL, FK(`users.id`) ON DELETE RESTRICT                | User who owns this quote snapshot    |
| `product_type`     | VARCHAR           | NOT NULL (RENT, LEASE, INSTALLMENT, CASH)                  | Type of financial product            |
| `vehicle_name`     | VARCHAR           | NULLABLE                                                   | Name of the vehicle                  |
| `vehicle_price`    | BIGINT            | NULLABLE                                                   | Base price of the vehicle            |
| `discount_amount`  | BIGINT            | NULLABLE                                                   | Applied discount                     |
| `deposit_amount`   | BIGINT            | NULLABLE                                                   | Deposit amount                       |
| `down_payment`     | BIGINT            | NULLABLE                                                   | Down payment amount                  |
| `monthly_payment`  | BIGINT            | NULLABLE                                                   | Monthly installment / rent fee       |
| `residual_value`   | BIGINT            | NULLABLE                                                   | Residual value of the vehicle        |
| `term_months`      | INTEGER           | NULLABLE                                                   | Duration of the contract in months   |
| `interest_rate`    | NUMERIC(5,2)      | NULLABLE                                                   | Applied interest rate                |
| `residual_rate`    | NUMERIC(5,2)      | NULLABLE                                                   | Residual value rate                  |
| `annual_mileage`   | INTEGER           | NULLABLE                                                   | Allowed annual mileage               |
| `capital_company`  | VARCHAR           | NULLABLE                                                   | Financial provider name              |
| `notes`            | TEXT              | NULLABLE                                                   | Additional remarks                   |
| `extra`            | JSONB             | DEFAULT '{}'                                               | Future-proof JSON payload            |
| `created_at`       | TIMESTAMP(TZ)     | DEFAULT now()                                              | Creation timestamp                   |
| `updated_at`       | TIMESTAMP(TZ)     | DEFAULT now()                                              | Last update timestamp                |

## Migration SQL (DDL)

```sql
CREATE TABLE quotes (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE RESTRICT,
    assigned_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    product_type VARCHAR NOT NULL,
    vehicle_name VARCHAR,
    vehicle_price BIGINT,
    discount_amount BIGINT,
    deposit_amount BIGINT,
    down_payment BIGINT,
    monthly_payment BIGINT,
    residual_value BIGINT,
    term_months INTEGER,
    interest_rate NUMERIC(5, 2),
    residual_rate NUMERIC(5, 2),
    annual_mileage INTEGER,
    capital_company VARCHAR,
    notes TEXT,
    extra JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quotes_company_id ON quotes(company_id);
CREATE INDEX idx_quotes_opportunity_id ON quotes(opportunity_id);
CREATE INDEX idx_quotes_assigned_user_id ON quotes(assigned_user_id);
```

## Rollback SQL

```sql
DROP TABLE IF EXISTS quotes;
```

## Security / RBAC Verification Check
- Row Level Security (RLS) policies are managed at the application level via SQLAlchemy, filtering uniformly by `company_id`.
- Foreign key cascading is strictly prohibited for `assigned_user_id` to prevent accidental loss of financial data if a user is hard-deleted. Use `RESTRICT` instead.
- The `quotes` endpoints perform dual checks: ensuring the `Quote` belongs to the `Company` and that `USER` role users can only act upon Quotes where `assigned_user_id == current_user.id`.

## Status
- **Pending**: Ready for execution via Supabase SQL Editor in a controlled manner upon user approval.
