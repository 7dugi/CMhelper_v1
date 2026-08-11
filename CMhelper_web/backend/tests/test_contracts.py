import os
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["CMHELPER_INVITE_CODE"] = "TEST-INVITE"
os.environ["CMHELPER_OWNER_EMAIL"] = "owner@test.com"
os.environ["CMHELPER_DEFAULT_COMPANY_NAME"] = "Test Company"
os.environ["CMHELPER_DEFAULT_COMPANY_SLUG"] = "test-company"

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from app.main import app

# We assume standard setup fixtures are available in conftest or can be mocked if needed.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
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
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True, scope="module")
def override_db_dependency():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture(scope="module")
def db_session(override_db_dependency):
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def get_auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def setup_data(db_session, client):
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
    
    from app.main import create_access_token
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

def test_create_contract_basic(client, setup_data):
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

def test_create_contract_invalid_date(client, setup_data):
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "contract_date": "2023-02-29", 
        "term_months": 24,
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 422
    
def test_create_contract_negative_term(client, setup_data):
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "contract_date": "2023-05-01",
        "term_months": -12,
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 422

def test_create_contract_user_assigns_other(client, setup_data):
    headers = get_auth_headers(setup_data["user1_token"])
    data = {
        "customer_id": setup_data["customer"].id,
        "assigned_user_id": setup_data["user2"].id,
        "contract_date": "2023-05-01",
        "term_months": 24,
    }
    resp = client.post("/api/contracts", json=data, headers=headers)
    assert resp.status_code == 403

def test_create_contract_owner_assigns_other(client, setup_data):
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

def test_update_contract_status_user_valid(client, setup_data, db_session):
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

def test_update_contract_status_user_invalid(client, setup_data, db_session):
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

def test_update_contract_status_owner_valid(client, setup_data, db_session):
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

def test_delete_contract_blocked(client, setup_data, db_session):
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

def test_legacy_dual_write_prevention(client, setup_data, db_session):
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

def test_expiry_date_recalculation(client, setup_data, db_session):
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
