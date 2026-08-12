import os
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["CMHELPER_INVITE_CODE"] = "TEST-INVITE"
os.environ["CMHELPER_OWNER_EMAIL"] = "owner@test.com"
os.environ["CMHELPER_DEFAULT_COMPANY_NAME"] = "Test Company"
os.environ["CMHELPER_DEFAULT_COMPANY_SLUG"] = "test-company"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import User, Company, Customer, Opportunity, UserRole, UserStatus
from app.main import app, create_access_token

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
    company2 = Company(name="OtherCompany", slug="other_company", status="ACTIVE")
    db_session.add_all([company, company2])
    db_session.commit()
    
    owner = User(company_id=company.id, email="owner@test.com", password_hash="fake", name="Owner User", role=UserRole.OWNER.value, status=UserStatus.ACTIVE.value)
    user1 = User(company_id=company.id, email="user1@test.com", password_hash="fake", name="User One", role=UserRole.USER.value, status=UserStatus.ACTIVE.value)
    other_owner = User(company_id=company2.id, email="other_owner@test.com", password_hash="fake", name="Other Owner", role=UserRole.OWNER.value, status=UserStatus.ACTIVE.value)
    other_user = User(company_id=company2.id, email="other_user@test.com", password_hash="fake", name="Other User", role=UserRole.USER.value, status=UserStatus.ACTIVE.value)
    inactive_user = User(company_id=company.id, email="inact@test.com", password_hash="fake", name="Inactive", role=UserRole.USER.value, status=UserStatus.PENDING.value)
    
    db_session.add_all([owner, user1, other_owner, other_user, inactive_user])
    db_session.commit()
    
    owner_token = create_access_token({"sub": str(owner.id), "role": "OWNER", "company_id": company.id})
    user1_token = create_access_token({"sub": str(user1.id), "role": "USER", "company_id": company.id})
    other_owner_token = create_access_token({"sub": str(other_owner.id), "role": "OWNER", "company_id": company2.id})
    
    customer = Customer(company_id=company.id, assigned_user_id=owner.id, name="Test Customer 1")
    db_session.add(customer)
    db_session.commit()
    
    return {
        "company": company,
        "owner": owner, "owner_token": owner_token,
        "user1": user1, "user1_token": user1_token,
        "other_owner": other_owner, "other_owner_token": other_owner_token,
        "other_user": other_user,
        "inactive_user": inactive_user,
        "customer": customer
    }

def create_mock_opportunity(db_session, company_id, user_id, cust_id):
    opp = Opportunity(company_id=company_id, customer_id=cust_id, assigned_user_id=user_id, title="opp")
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)
    return opp

@pytest.fixture
def quote_payload():
    return {
        "product_type": "RENT",
        "vehicle_name": "Hyundai Sonata",
        "vehicle_price": 30000000,
        "discount_amount": 1000000,
        "deposit_amount": 0,
        "down_payment": 0,
        "monthly_payment": 500000,
        "residual_value": 10000000,
        "term_months": 48,
        "interest_rate": 4.5,
        "residual_rate": 33.3,
        "annual_mileage": 20000,
        "capital_company": "Hyundai Capital",
        "notes": "Test note"
    }

def test_quote_create_owner_success(client, setup_data, db_session, quote_payload):
    opp = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp.id
    
    headers = get_auth_headers(setup_data["owner_token"])
    res = client.post("/api/quotes", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["assigned_user_id"] == setup_data["owner"].id

    payload["assigned_user_id"] = setup_data["user1"].id
    res = client.post("/api/quotes", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["assigned_user_id"] == setup_data["user1"].id

def test_quote_create_owner_fail(client, setup_data, db_session, quote_payload):
    opp = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp.id
    headers = get_auth_headers(setup_data["owner_token"])

    payload["assigned_user_id"] = setup_data["other_user"].id
    res = client.post("/api/quotes", json=payload, headers=headers)
    assert res.status_code == 400

    payload["assigned_user_id"] = setup_data["inactive_user"].id
    res = client.post("/api/quotes", json=payload, headers=headers)
    assert res.status_code == 400

    payload["assigned_user_id"] = 99999
    res = client.post("/api/quotes", json=payload, headers=headers)
    assert res.status_code == 400

def test_quote_create_user(client, setup_data, db_session, quote_payload):
    opp = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["user1"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp.id
    headers = get_auth_headers(setup_data["user1_token"])

    res = client.post("/api/quotes", json=payload, headers=headers)
    assert res.status_code == 200

    opp_other = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    payload["opportunity_id"] = opp_other.id
    res = client.post("/api/quotes", json=payload, headers=headers)
    assert res.status_code == 403

    payload["opportunity_id"] = opp.id
    payload["assigned_user_id"] = setup_data["owner"].id
    res = client.post("/api/quotes", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["assigned_user_id"] == setup_data["user1"].id

def test_quote_tenant_isolation(client, setup_data, db_session, quote_payload):
    opp = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp.id

    res = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
    quote_id = res.json()["id"]

    other_headers = get_auth_headers(setup_data["other_owner_token"])
    res = client.post("/api/quotes", json=payload, headers=other_headers)
    assert res.status_code in [403, 404]

    res = client.get(f"/api/quotes/{quote_id}", headers=other_headers)
    assert res.status_code in [403, 404]

    res = client.patch(f"/api/quotes/{quote_id}", json={"notes": "hacked"}, headers=other_headers)
    assert res.status_code in [403, 404]

def test_quote_list(client, setup_data, db_session, quote_payload):
    opp1 = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["user1"].id, setup_data["customer"].id)
    opp2 = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp1.id
    client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["user1_token"]))
    
    payload["opportunity_id"] = opp2.id
    client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))

    res = client.get("/api/quotes", headers=get_auth_headers(setup_data["user1_token"]))
    assert res.status_code == 200
    assert len(res.json()) >= 1
    for q in res.json():
        assert q["assigned_user_id"] == setup_data["user1"].id

    res = client.get(f"/api/quotes?assigned_user_id={setup_data['owner'].id}", headers=get_auth_headers(setup_data["user1_token"]))
    for q in res.json():
        assert q["assigned_user_id"] == setup_data["user1"].id

    res = client.get("/api/quotes", headers=get_auth_headers(setup_data["owner_token"]))
    assert len(res.json()) >= 2

def test_quote_update(client, setup_data, db_session, quote_payload):
    opp = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp.id
    res = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
    quote_id = res.json()["id"]

    res = client.patch(f"/api/quotes/{quote_id}", json={"assigned_user_id": setup_data["user1"].id}, headers=get_auth_headers(setup_data["owner_token"]))
    assert res.status_code == 200
    assert res.json()["assigned_user_id"] == setup_data["user1"].id

    res = client.patch(f"/api/quotes/{quote_id}", json={"assigned_user_id": setup_data["other_user"].id}, headers=get_auth_headers(setup_data["owner_token"]))
    assert res.status_code == 400

    res = client.patch(f"/api/quotes/{quote_id}", json={"assigned_user_id": setup_data["owner"].id}, headers=get_auth_headers(setup_data["user1_token"]))
    assert res.status_code == 403

def test_quote_delete(client, setup_data, db_session, quote_payload):
    opp_owner = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp_owner.id
    res_owner = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
    quote_id_owner = res_owner.json()["id"]

    res = client.delete(f"/api/quotes/{quote_id_owner}", headers=get_auth_headers(setup_data["user1_token"]))
    assert res.status_code in [403, 404]

    res = client.delete(f"/api/quotes/{quote_id_owner}", headers=get_auth_headers(setup_data["other_owner_token"]))
    assert res.status_code in [403, 404]

    res = client.delete(f"/api/quotes/{quote_id_owner}", headers=get_auth_headers(setup_data["owner_token"]))
    assert res.status_code == 409

    opp_user = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["user1"].id, setup_data["customer"].id)
    payload["opportunity_id"] = opp_user.id
    res_user = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["user1_token"]))
    quote_id_user = res_user.json()["id"]

    res = client.delete(f"/api/quotes/{quote_id_user}", headers=get_auth_headers(setup_data["user1_token"]))
    assert res.status_code == 409

def test_quote_structure(client, setup_data, db_session, quote_payload):
    opp = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    
    types = ["RENT", "LEASE", "INSTALLMENT", "CASH"]
    for t in types:
        payload = quote_payload.copy()
        payload["opportunity_id"] = opp.id
        payload["product_type"] = t
        res = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
        assert res.status_code == 200

    res = client.get(f"/api/opportunities/{opp.id}/quotes", headers=get_auth_headers(setup_data["owner_token"]))
    assert len(res.json()) >= 4

def test_quote_validation(client, setup_data, db_session, quote_payload):
    opp = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp.id

    payload["product_type"] = "INVALID"
    res = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
    assert res.status_code == 422
    payload["product_type"] = "RENT"

    payload["vehicle_price"] = -100
    res = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
    assert res.status_code == 422
    payload["vehicle_price"] = 100

    payload["term_months"] = 0
    res = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
    assert res.status_code == 422
    payload["term_months"] = 48

    payload["interest_rate"] = -1.5
    res = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
    assert res.status_code == 422
def test_quote_update_inactive(client, setup_data, db_session, quote_payload):
    opp = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["owner"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp.id
    res = client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))
    quote_id = res.json()["id"]
    
    # 18: OWNER Inactive User 재배정 실패
    res = client.patch(f"/api/quotes/{quote_id}", json={"assigned_user_id": setup_data["inactive_user"].id}, headers=get_auth_headers(setup_data["owner_token"]))
    assert res.status_code == 400

    # Quote PATCH opportunity_id 불가, company_id 불가
    res = client.patch(f"/api/quotes/{quote_id}", json={"opportunity_id": 9999, "company_id": 9999}, headers=get_auth_headers(setup_data["owner_token"]))
    # Base model ignores them, so it's 200 but values should be unchanged
    assert res.status_code == 200
    assert res.json()["opportunity_id"] == opp.id
    assert res.json()["company_id"] == setup_data["company"].id

def test_opportunity_quote_list_isolation(client, setup_data, db_session, quote_payload):
    # OWNER creates quote assigned to user1 inside user1's opportunity
    opp_user = create_mock_opportunity(db_session, setup_data["company"].id, setup_data["user1"].id, setup_data["customer"].id)
    payload = quote_payload.copy()
    payload["opportunity_id"] = opp_user.id
    payload["assigned_user_id"] = setup_data["user1"].id
    client.post("/api/quotes", json=payload, headers=get_auth_headers(setup_data["owner_token"]))

    # OWNER creates quote assigned to owner inside the SAME opportunity (if OWNER decided to intervene)
    payload2 = quote_payload.copy()
    payload2["opportunity_id"] = opp_user.id
    payload2["assigned_user_id"] = setup_data["owner"].id
    client.post("/api/quotes", json=payload2, headers=get_auth_headers(setup_data["owner_token"]))

    # OWNER lists quotes for opp_user - should see both
    res_owner = client.get(f"/api/opportunities/{opp_user.id}/quotes", headers=get_auth_headers(setup_data["owner_token"]))
    assert len(res_owner.json()) >= 2

    # USER lists quotes for opp_user - should see ONLY their own
    res_user = client.get(f"/api/opportunities/{opp_user.id}/quotes", headers=get_auth_headers(setup_data["user1_token"]))
    assert len(res_user.json()) == 1
    assert res_user.json()[0]["assigned_user_id"] == setup_data["user1"].id


def test_quote_retention_policy():
    from app.models import Quote
    
    # Extract foreign keys mapped by column name
    fks = {fk.parent.name: fk for fk in Quote.__table__.foreign_keys}
    
    # Ensure deleting an opportunity does NOT cascade delete quotes
    assert fks['opportunity_id'].ondelete == 'RESTRICT'
    
    # Ensure deleting a user does NOT cascade delete quotes
    assert fks['assigned_user_id'].ondelete == 'RESTRICT'
    
    # Deleting a company (tenant) should cascade
    assert fks['company_id'].ondelete == 'CASCADE'
