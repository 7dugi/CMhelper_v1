import os
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["CMHELPER_INVITE_CODE"] = "TEST-INVITE"
os.environ["CMHELPER_OWNER_EMAIL"] = "owner@test.com"
os.environ["CMHELPER_DEFAULT_COMPANY_NAME"] = "Test Company"
os.environ["CMHELPER_DEFAULT_COMPANY_SLUG"] = "test-company"

import pytest
from sqlalchemy import create_engine, text, inspect
from unittest.mock import MagicMock

from app.database import Base
from app.main import run_migrations
import app.models  # ensure models are registered


def test_fresh_sqlite_migration_and_idempotency():
    """Verify fresh SQLite create_all + run_migrations produces columns, indexes, and is idempotent."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    # Run migrations 3 times to prove idempotency
    run_migrations(engine)
    run_migrations(engine)
    run_migrations(engine)

    inspector = inspect(engine)

    # 1. Verify contracts table columns
    cols = {col["name"]: col for col in inspector.get_columns("contracts")}
    assert "source_opportunity_id" in cols
    assert "source_quote_id" in cols
    assert "monthly_payment" in cols

    # 2. Verify contracts table indexes
    indexes = inspector.get_indexes("contracts")
    index_names = {idx["name"] for idx in indexes}
    assert "uq_contracts_source_opportunity_id" in index_names
    assert "ix_contracts_source_quote_id" in index_names

    # Verify unique index property
    uq_idx = next(idx for idx in indexes if idx["name"] == "uq_contracts_source_opportunity_id")
    assert uq_idx["unique"] is True or uq_idx["unique"] == 1

    # 3. Verify other migrated tables
    cust_cols = {c["name"] for c in inspector.get_columns("customers")}
    assert "extra" in cust_cols
    assert "sent_quotes" in cust_cols
    assert "is_prospect" in cust_cols
    assert "is_contracted" in cust_cols

    fd_cols = {c["name"] for c in inspector.get_columns("field_definitions")}
    assert "target_type" in fd_cols

    mt_cols = {c["name"] for c in inspector.get_columns("message_tasks")}
    assert "scheduled_at" in mt_cols


def test_existing_sqlite_simulation_and_no_fk_retrofit():
    """Simulate pre-existing SQLite database without Phase 3D columns and verify forward-only migration with no FK retrofit."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    # Create pre-existing tables with older schema
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR NOT NULL, company_id INTEGER NOT NULL)"))
        conn.execute(text("CREATE TABLE field_definitions (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR NOT NULL)"))
        conn.execute(text("CREATE TABLE message_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title VARCHAR NOT NULL)"))
        conn.execute(text("""
            CREATE TABLE contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                assigned_user_id INTEGER NOT NULL,
                vehicle_model VARCHAR,
                product_type VARCHAR,
                capital VARCHAR,
                contract_date VARCHAR,
                term_months INTEGER,
                expiry_date VARCHAR,
                dealer_info VARCHAR,
                insurance_active BOOLEAN DEFAULT 0,
                supplies_work VARCHAR,
                estimate_image VARCHAR,
                status VARCHAR DEFAULT 'ACTIVE' NOT NULL,
                memo VARCHAR,
                legacy_origin_customer_id INTEGER UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """))

    inspector_before = inspect(engine)
    cols_before = {col["name"] for col in inspector_before.get_columns("contracts")}
    assert "source_opportunity_id" not in cols_before
    assert "source_quote_id" not in cols_before
    assert "monthly_payment" not in cols_before

    # Run migrations 3 times to prove forward-only idempotency
    run_migrations(engine)
    run_migrations(engine)
    run_migrations(engine)

    inspector_after = inspect(engine)
    cols_after = {col["name"]: col for col in inspector_after.get_columns("contracts")}
    assert "source_opportunity_id" in cols_after
    assert "source_quote_id" in cols_after
    assert "monthly_payment" in cols_after

    # Verify indexes created on SQLite
    indexes = inspector_after.get_indexes("contracts")
    index_names = {idx["name"] for idx in indexes}
    assert "uq_contracts_source_opportunity_id" in index_names
    assert "ix_contracts_source_quote_id" in index_names

    # Verify no foreign keys retrofitted into SQLite (no table rebuild was performed)
    fks = inspector_after.get_foreign_keys("contracts")
    fk_cols = [fk["constrained_columns"] for fk in fks]
    assert not any("source_opportunity_id" in cols for cols in fk_cols)
    assert not any("source_quote_id" in cols for cols in fk_cols)

    # Verify unique index enforcement on SQLite
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO contracts (company_id, customer_id, assigned_user_id, source_opportunity_id) VALUES (1, 1, 1, 100)"))
        with pytest.raises(Exception):
            conn.execute(text("INSERT INTO contracts (company_id, customer_id, assigned_user_id, source_opportunity_id) VALUES (1, 1, 1, 100)"))


def test_postgres_migration_sql_generation():
    """Verify PostgreSQL migration path queries table_constraints and adds constraints idempotently."""
    mock_eng = MagicMock()
    mock_eng.dialect.name = "postgresql"

    mock_conn = MagicMock()
    mock_eng.begin.return_value.__enter__.return_value = mock_conn

    # First run: no existing columns or constraints
    mock_conn.execute.return_value.fetchall.return_value = []

    run_migrations(mock_eng)

    executed_statements = [str(call.args[0]) for call in mock_conn.execute.call_args_list]

    # Verify constraint addition queries on PostgreSQL
    assert any("fk_contracts_source_opportunity_id" in s and "FOREIGN KEY" in s for s in executed_statements)
    assert any("fk_contracts_source_quote_id" in s and "FOREIGN KEY" in s for s in executed_statements)
    assert any("uq_contracts_source_opportunity_id" in s and "UNIQUE" in s for s in executed_statements)
    assert any("ix_contracts_source_quote_id" in s for s in executed_statements)


def test_postgres_migration_idempotency_when_constraints_exist():
    """Verify PostgreSQL migration skips adding constraints if they already exist in information_schema."""
    mock_eng = MagicMock()
    mock_eng.dialect.name = "postgresql"

    mock_conn = MagicMock()
    mock_eng.begin.return_value.__enter__.return_value = mock_conn

    # Simulate existing columns and constraints
    def mock_execute(stmt):
        s = str(stmt)
        result_mock = MagicMock()
        if "information_schema.columns" in s:
            result_mock.fetchall.return_value = [
                ("contact",), ("region",), ("contract_date",), ("contract_months",),
                ("expiry_date",), ("capital",), ("product_type",), ("is_prospect",),
                ("is_contracted",), ("anniversary",), ("memo",), ("estimate_image",),
                ("sent_quotes",), ("extra",), ("target_type",), ("scheduled_at",),
                ("source_opportunity_id",), ("source_quote_id",), ("monthly_payment",)
            ]
        elif "information_schema.table_constraints" in s:
            result_mock.fetchall.return_value = [
                ("fk_contracts_source_opportunity_id",),
                ("fk_contracts_source_quote_id",),
                ("uq_contracts_source_opportunity_id",)
            ]
        else:
            result_mock.fetchall.return_value = []
        return result_mock

    mock_conn.execute.side_effect = mock_execute

    run_migrations(mock_eng)

    executed_statements = [str(call.args[0]) for call in mock_conn.execute.call_args_list]
    assert not any("ADD CONSTRAINT" in s for s in executed_statements)
