import os
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["CMHELPER_INVITE_CODE"] = "TEST-INVITE"
os.environ["CMHELPER_OWNER_EMAIL"] = "owner@test.com"
os.environ["CMHELPER_DEFAULT_COMPANY_NAME"] = "Test Company"
os.environ["CMHELPER_DEFAULT_COMPANY_SLUG"] = "test-company"

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app, create_access_token, run_migrations
from app.database import Base, get_db
from app.models import User, Company, Customer, Contract

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def override_db_dependency():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def setup_data(db_session):
    company = Company(name="TestCompany", slug="test_company", status="ACTIVE")
    db_session.add(company)
    db_session.commit()
    
    owner = User(
        company_id=company.id,
        email="owner@test.com",
        password_hash="fake",
        name="Owner User",
        role="OWNER",
        status="ACTIVE"
    )
    user1 = User(
        company_id=company.id,
        email="user1@test.com",
        password_hash="fake",
        name="User One",
        role="USER",
        status="ACTIVE"
    )
    user2 = User(
        company_id=company.id,
        email="user2@test.com",
        password_hash="fake",
        name="User Two",
        role="USER",
        status="ACTIVE"
    )
    
    db_session.add_all([owner, user1, user2])
    db_session.commit()
    
    owner_token = create_access_token({"sub": str(owner.id), "role": "OWNER", "company_id": company.id})
    user1_token = create_access_token({"sub": str(user1.id), "role": "USER", "company_id": company.id})
    user2_token = create_access_token({"sub": str(user2.id), "role": "USER", "company_id": company.id})
    
    customer = Customer(
        company_id=company.id,
        assigned_user_id=user1.id,
        name="Test Customer 1",
        contact="010-1234-5678",
    )
    db_session.add(customer)
    db_session.commit()
    
    return {
        "company": company,
        "owner": owner,
        "owner_token": owner_token,
        "user1": user1,
        "user1_token": user1_token,
        "user2": user2,
        "user2_token": user2_token,
        "customer": customer
    }

def test_create_contract_basic(setup_data):
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "vehicle_model": "Tesla Model Y",
        "contract_date": "2023-05-01",
        "term_months": 24,
        "status": "ACTIVE"
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 201
    contract = resp.json()
    assert contract["assigned_user_id"] == setup_data["user1"].id
    assert contract["status"] == "ACTIVE"
    assert contract["expiry_date"] == "2025-05-01"
    assert contract["source_opportunity_id"] is None
    assert contract["source_quote_id"] is None
    assert contract["monthly_payment"] is None

def test_manual_contract_create_omitted_source_fields_and_monthly_payment(setup_data):
    """Verify manual Contract creation with omitted source fields and omitted monthly_payment succeeds and defaults to None."""
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "vehicle_model": "Genesis GV80",
        "product_type": "LEASE",
        "capital": "Hyundai Capital",
        "contract_date": "2024-06-01",
        "term_months": 36,
        "status": "ACTIVE"
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 201
    contract = resp.json()
    assert contract["vehicle_model"] == "Genesis GV80"
    assert contract["source_opportunity_id"] is None
    assert contract["source_quote_id"] is None
    assert contract["monthly_payment"] is None
    assert contract["expiry_date"] == "2027-06-01"

def test_manual_contract_patch_omitted_source_fields(setup_data, db_session):
    """Verify manual Contract patch without source fields preserves None and updates target attributes."""
    c = Contract(
        company_id=setup_data["company"].id,
        customer_id=setup_data["customer"].id,
        assigned_user_id=setup_data["user1"].id,
        vehicle_model="Avante",
        contract_date="2024-01-01",
        term_months=12,
        status="ACTIVE",
        memo="Initial memo"
    )
    db_session.add(c)
    db_session.commit()
    contract_id = c.id

    headers = get_auth_headers(setup_data["user1_token"])
    resp = client.patch(f"/api/contracts/{contract_id}", json={
        "memo": "Updated memo without source fields",
        "dealer_info": "Gangnam Branch"
    }, headers=headers)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["memo"] == "Updated memo without source fields"
    assert updated["dealer_info"] == "Gangnam Branch"
    assert updated["source_opportunity_id"] is None
    assert updated["source_quote_id"] is None
    assert updated["monthly_payment"] is None

def test_manual_contract_list_omitted_source_fields(setup_data, db_session):
    """Verify GET /api/contracts returns contracts with omitted source fields and monthly_payment as None."""
    c1 = Contract(
        company_id=setup_data["company"].id,
        customer_id=setup_data["customer"].id,
        assigned_user_id=setup_data["user1"].id,
        vehicle_model="Sonata",
        status="ACTIVE"
    )
    c2 = Contract(
        company_id=setup_data["company"].id,
        customer_id=setup_data["customer"].id,
        assigned_user_id=setup_data["user1"].id,
        vehicle_model="Grandeur",
        status="ACTIVE"
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    headers = get_auth_headers(setup_data["user1_token"])
    resp = client.get("/api/contracts", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 2
    for item in items:
        assert "source_opportunity_id" in item
        assert "source_quote_id" in item
        assert "monthly_payment" in item
        assert item["source_opportunity_id"] is None
        assert item["source_quote_id"] is None
        assert item["monthly_payment"] is None

def test_create_contract_invalid_date(setup_data):
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "contract_date": "2023-02-29", 
        "term_months": 24,
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 422
    
def test_create_contract_negative_term(setup_data):
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "contract_date": "2023-05-01",
        "term_months": -12,
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 422

def test_create_contract_user_assigns_other(setup_data):
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "assigned_user_id": setup_data["user2"].id,
        "contract_date": "2023-05-01",
        "term_months": 24,
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 403

def test_create_contract_owner_assigns_other(setup_data):
    headers = get_auth_headers(setup_data["owner_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "assigned_user_id": setup_data["user2"].id,
        "contract_date": "2023-05-01",
        "term_months": 24,
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 201
    contract = resp.json()
    assert contract["assigned_user_id"] == setup_data["user2"].id

def test_update_contract_status_user_valid(setup_data, db_session):
    c = Contract(
        company_id=setup_data["company"].id,
        customer_id=setup_data["customer"].id,
        assigned_user_id=setup_data["user1"].id,
        status="ACTIVE"
    )
    db_session.add(c)
    db_session.commit()
    
    headers = get_auth_headers(setup_data["user1_token"])
    resp = client.patch(f"/api/contracts/{c.id}", json={"status": "COMPLETED"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"

def test_update_contract_status_user_invalid(setup_data, db_session):
    c = Contract(
        company_id=setup_data["company"].id,
        customer_id=setup_data["customer"].id,
        assigned_user_id=setup_data["user1"].id,
        status="COMPLETED"
    )
    db_session.add(c)
    db_session.commit()
    
    headers = get_auth_headers(setup_data["user1_token"])
    resp = client.patch(f"/api/contracts/{c.id}", json={"status": "CANCELLED"}, headers=headers)
    assert resp.status_code == 403

def test_update_contract_status_owner_valid(setup_data, db_session):
    c = Contract(
        company_id=setup_data["company"].id,
        customer_id=setup_data["customer"].id,
        assigned_user_id=setup_data["user1"].id,
        status="COMPLETED"
    )
    db_session.add(c)
    db_session.commit()
    
    headers = get_auth_headers(setup_data["owner_token"])
    resp = client.patch(f"/api/contracts/{c.id}", json={"status": "ACTIVE"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"

def test_delete_contract_blocked(setup_data, db_session):
    c = Contract(
        company_id=setup_data["company"].id,
        customer_id=setup_data["customer"].id,
        assigned_user_id=setup_data["user1"].id,
        status="ACTIVE"
    )
    db_session.add(c)
    db_session.commit()
    
    headers = get_auth_headers(setup_data["owner_token"])
    resp = client.delete(f"/api/contracts/{c.id}", headers=headers)
    assert resp.status_code == 409
    
    c_check = db_session.query(Contract).filter(Contract.id == c.id).first()
    assert c_check is not None

def test_legacy_dual_write_prevention(setup_data, db_session):
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "contract_date": "2024-01-01",
        "term_months": 12,
    }
    client.post("/api/contracts", json=data, headers=headers)
    
    db_session.refresh(setup_data["customer"])
    assert setup_data["customer"].contract_date is None
    assert setup_data["customer"].contract_months is None

def test_expiry_date_recalculation(setup_data, db_session):
    c = Contract(
        company_id=setup_data["company"].id,
        customer_id=setup_data["customer"].id,
        assigned_user_id=setup_data["user1"].id,
        contract_date="2024-02-01",
        term_months=12,
        status="ACTIVE"
    )
    db_session.add(c)
    db_session.commit()
    
    headers = get_auth_headers(setup_data["owner_token"])
    resp = client.patch(f"/api/contracts/{c.id}", json={"contract_date": "2024-03-01"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["expiry_date"] == "2025-03-01"
