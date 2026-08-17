import os
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["CMHELPER_INVITE_CODE"] = "TEST-INVITE"
os.environ["CMHELPER_OWNER_EMAIL"] = "owner@test.com"
os.environ["CMHELPER_DEFAULT_COMPANY_NAME"] = "Test Company"
os.environ["CMHELPER_DEFAULT_COMPANY_SLUG"] = "test-company"

import pytest
from fastapi.testclient import TestClient
from app.main import app

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.models import User, Company, Customer, Opportunity, Quote, Contract, UserRole, UserStatus
from app.main import create_access_token
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    from app.main import run_migrations
    run_migrations(engine)
    
    db = TestingSessionLocal()
    # Create companies
    c1 = Company(name="Test Co", slug="test-co")
    c2 = Company(name="Other Co", slug="other-co")
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)
    
    # Create users
    u1 = User(email="owner1@test.com", password_hash="pw", name="O1", role=UserRole.OWNER.value, company_id=c1.id)
    u2 = User(email="user1@test.com", password_hash="pw", name="U1", role=UserRole.USER.value, company_id=c1.id)
    u3 = User(email="user2@test.com", password_hash="pw", name="U2", role=UserRole.USER.value, company_id=c1.id)
    u4 = User(email="owner2@test.com", password_hash="pw", name="O2", role=UserRole.OWNER.value, company_id=c2.id)
    db.add_all([u1, u2, u3, u4])
    db.commit()
    
    # Create customers
    cust1 = Customer(name="Cust1", contact="010-1111", company_id=c1.id, assigned_user_id=u1.id)
    cust2 = Customer(name="Cust2", contact="010-2222", company_id=c2.id, assigned_user_id=u4.id)
    db.add_all([cust1, cust2])
    db.commit()
    
    
    yield
    Base.metadata.drop_all(bind=engine)

def get_token(user_id):
    db = TestingSessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    
    return create_access_token(data={"sub": str(user.id)})

def test_conversion_success():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=2, status="WON", title="Opp1")
    db.add(opp)
    db.commit()
    db.refresh(opp)
    
    quote = Quote(company_id=1, opportunity_id=opp.id, assigned_user_id=2, vehicle_name="Car", product_type="LEASE", capital_company="Lotte", term_months=48, monthly_payment=500000)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    
    token = get_token(2)
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={
        "source_quote_id": quote.id,
        "vehicle_model": "Car",
        "monthly_payment": 500000
    })
    
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_opportunity_id"] == opp.id
    assert data["source_quote_id"] == quote.id
    assert data["monthly_payment"] == 500000
    assert data["customer_id"] == opp.customer_id
    assert data["monthly_payment"] == 500000
    assert data["customer_id"] == 1
    assert data["assigned_user_id"] == 2 # USER is forced to self

def test_duplicate_conversion():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=2, status="WON", title="Opp2")
    db.add(opp)
    db.commit()
    db.refresh(opp)
    
    token = get_token(2)
    payload = {"vehicle_model": "Car"}
    # First conversion
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp.status_code == 201
    
    # Second conversion (duplicate)
    resp2 = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp2.status_code == 409

def test_not_won():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=2, status="QUOTING", title="Opp3")
    db.add(opp)
    db.commit()
    db.refresh(opp)
    
    token = get_token(2)
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"vehicle_model": "Car"})
    assert resp.status_code == 400

def test_cross_tenant_isolation():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=1, status="WON", title="Opp4")
    db.add(opp)
    db.commit()
    db.refresh(opp)
    
    # user from company 2 tries to convert company 1 opportunity
    token = get_token(4) 
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"vehicle_model": "Car"})
    assert resp.status_code == 404

def test_user_wrong_assignment():
    db = TestingSessionLocal()
    # assigned to u3
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=3, status="WON", title="Opp5")
    db.add(opp)
    db.commit()
    db.refresh(opp)
    
    # u2 tries to convert
    token = get_token(2)
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"vehicle_model": "Car"})
    assert resp.status_code == 403

def test_owner_can_assign_other():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=2, status="WON", title="Opp6")
    db.add(opp)
    db.commit()
    db.refresh(opp)
    
    # owner u1 converts and assigns to u3
    token = get_token(1)
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={
        "assigned_user_id": 3,
        "vehicle_model": "Car"
    })
    assert resp.status_code == 201
    assert resp.json()["assigned_user_id"] == 3

def test_wrong_quote_relation():
    db = TestingSessionLocal()
    opp1 = Opportunity(company_id=1, customer_id=1, assigned_user_id=1, status="WON", title="Opp7")
    opp2 = Opportunity(company_id=1, customer_id=1, assigned_user_id=1, status="WON", title="Opp8")
    db.add_all([opp1, opp2])
    db.commit()
    db.refresh(opp1)
    db.refresh(opp2)
    
    # quote belongs to opp2
    quote = Quote(company_id=1, opportunity_id=opp2.id, assigned_user_id=1, product_type="LEASE", vehicle_name="Car")
    db.add(quote)
    db.commit()
    db.refresh(quote)
    
    token = get_token(1)
    # try converting opp1 using quote from opp2
    resp = client.post(f"/api/opportunities/{opp1.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={
        "source_quote_id": quote.id
    })
    assert resp.status_code == 404

def test_conversion_success_no_quote():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=1, status="WON", title="Opp_no_quote")
    db.add(opp)
    db.commit()
    db.refresh(opp)

    token = get_token(1)
    payload = {"vehicle_model": "Car2"}
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_opportunity_id"] == opp.id
    assert data["source_quote_id"] is None
    assert data["customer_id"] == opp.customer_id

def test_cross_tenant_quote():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=1, status="WON", title="Opp_cross_quote")
    db.add(opp)
    db.commit()
    db.refresh(opp)

    # quote from company 2
    quote = Quote(company_id=2, opportunity_id=opp.id, assigned_user_id=1, product_type="LEASE", vehicle_name="Car")
    db.add(quote)
    db.commit()
    db.refresh(quote)

    token = get_token(1)
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"source_quote_id": quote.id})
    assert resp.status_code == 404

def test_user_cannot_reassign():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=2, status="WON", title="Opp_reassign")
    db.add(opp)
    db.commit()
    db.refresh(opp)

    token = get_token(2)
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"assigned_user_id": 3})
    assert resp.status_code == 201
    assert resp.json()["assigned_user_id"] == 2

def test_owner_assign_cross_tenant():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=1, status="WON", title="Opp_owner_assign")
    db.add(opp)
    db.commit()
    db.refresh(opp)

    token = get_token(1) # owner of company 1
    # User 4 is company 2
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"assigned_user_id": 4})
    assert resp.status_code == 400
    assert "Invalid assigned_user_id" in resp.json()["detail"]

def test_owner_assign_inactive():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=1, status="WON", title="Opp_inactive")
    db.add(opp)
    # create inactive user in company 1
    u = User(company_id=1, email="inactive@a.com", name="I", password_hash="pw", role="USER", status="INACTIVE")
    db.add(u)
    db.commit()
    db.refresh(opp)
    db.refresh(u)

    token = get_token(1)
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"assigned_user_id": u.id})
    assert resp.status_code == 400

def test_not_won_new():
    db = TestingSessionLocal()
    opp = Opportunity(company_id=1, customer_id=1, assigned_user_id=2, status="NEW", title="Opp3_new")
    db.add(opp)
    db.commit()
    db.refresh(opp)
    token = get_token(2)
    resp = client.post(f"/api/opportunities/{opp.id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"vehicle_model": "Car"})
    assert resp.status_code == 400
