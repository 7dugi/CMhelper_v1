-- DO NOT RUN WITHOUT REVIEW
-- PHASE 2A DRAFT ONLY

CREATE TABLE IF NOT EXISTS contracts (
    id SERIAL PRIMARY KEY,
    -- WARNING: company_id has ON DELETE CASCADE.
    -- In current design, company hard-delete is NOT allowed, but if it happens, Contracts will be cascaded.
    -- Future company lifecycle (ACTIVE/INACTIVE/ARCHIVED) should be used instead.
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

-- Indexes for frequent queries
CREATE INDEX idx_contracts_company_id ON contracts(company_id);
CREATE INDEX idx_contracts_customer_id ON contracts(customer_id);
CREATE INDEX idx_contracts_assigned_user_id ON contracts(assigned_user_id);
CREATE INDEX idx_contracts_vehicle_model ON contracts(vehicle_model);
CREATE INDEX idx_contracts_expiry_date ON contracts(expiry_date);

-- Standard unique index for idempotency during migration (matches Production)
CREATE UNIQUE INDEX uq_contracts_legacy_origin ON contracts(legacy_origin_customer_id);
