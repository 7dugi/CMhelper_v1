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
from app.models import User, Company, Customer, Opportunity, Contract
from app.main import create_access_token

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

@pytest.fixture(autouse=True)
def override_db_dependency():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(override_db_dependency):
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def get_auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def setup_data(db_session, client):
    company = Company(name="TestCompany", slug="test_company", status="ACTIVE")
    company2 = Company(name="OtherCompany", slug="other_company", status="ACTIVE")
    db_session.add_all([company, company2])
    db_session.commit()
    
    owner = User(company_id=company.id, email="owner@test.com", password_hash="fake", name="Owner", role="OWNER", status="ACTIVE")
    user1 = User(company_id=company.id, email="user1@test.com", password_hash="fake", name="User 1", role="USER", status="ACTIVE")
    inactive_user = User(company_id=company.id, email="inactive@test.com", password_hash="fake", name="Inactive", role="USER", status="INACTIVE")
    user2 = User(company_id=company2.id, email="other@test.com", password_hash="fake", name="Other", role="USER", status="ACTIVE")
    
    db_session.add_all([owner, user1, inactive_user, user2])
    db_session.commit()
    
    return {
        "company": company,
        "company2": company2,
        "owner": owner,
        "user1": user1,
        "inactive_user": inactive_user,
        "user2": user2,
        "owner_headers": get_auth_headers(create_access_token({"sub": str(owner.id)})),
        "user_headers": get_auth_headers(create_access_token({"sub": str(user1.id)})),
        "other_headers": get_auth_headers(create_access_token({"sub": str(user2.id)}))
    }

# 6. OWNER Create Tests
def test_owner_create_auto_assign(client, setup_data):
    owner_headers = setup_data["owner_headers"]
    customer = client.post("/api/customers", headers=owner_headers, json={"name": "Cust"}).json()
    
    # A. OWNER create + assigned_user_id 없음 -> Customer 담당자 자동 승계
    res = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": customer["id"], "title": "Opp A"})
    assert res.status_code == 201
    assert res.json()["assigned_user_id"] == setup_data["owner"].id

def test_owner_create_assignee_validation(client, setup_data):
    owner_headers = setup_data["owner_headers"]
    customer = client.post("/api/customers", headers=owner_headers, json={"name": "Cust2"}).json()
    cid = customer["id"]

    # B. OWNER create + same-company ACTIVE User -> 성공
    res = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": cid, "title": "Opp B", "assigned_user_id": setup_data["user1"].id})
    assert res.status_code == 201
    assert res.json()["assigned_user_id"] == setup_data["user1"].id

    # C. OWNER create + cross-tenant User -> 실패
    res = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": cid, "title": "Opp C", "assigned_user_id": setup_data["user2"].id})
    assert res.status_code == 403

    # D. OWNER create + INACTIVE User -> 실패
    res = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": cid, "title": "Opp D", "assigned_user_id": setup_data["inactive_user"].id})
    assert res.status_code == 400

    # E. OWNER create + nonexistent User -> 실패
    res = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": cid, "title": "Opp E", "assigned_user_id": 9999})
    assert res.status_code == 404

# 7. OWNER Update Tests
def test_owner_update_reassign(client, setup_data):
    owner_headers = setup_data["owner_headers"]
    customer = client.post("/api/customers", headers=owner_headers, json={"name": "Cust"}).json()
    opp = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": customer["id"], "title": "Opp"}).json()
    oid = opp["id"]

    # A. same-company ACTIVE User로 reassignment -> 성공
    res = client.patch(f"/api/opportunities/{oid}", headers=owner_headers, json={"assigned_user_id": setup_data["user1"].id})
    assert res.status_code == 200

    # B. cross-tenant User로 reassignment -> 실패
    res = client.patch(f"/api/opportunities/{oid}", headers=owner_headers, json={"assigned_user_id": setup_data["user2"].id})
    assert res.status_code == 403

    # C. INACTIVE User로 reassignment -> 실패
    res = client.patch(f"/api/opportunities/{oid}", headers=owner_headers, json={"assigned_user_id": setup_data["inactive_user"].id})
    assert res.status_code == 400

    # D. nonexistent User -> 실패
    res = client.patch(f"/api/opportunities/{oid}", headers=owner_headers, json={"assigned_user_id": 9999})
    assert res.status_code == 404

# 8. USER Isolation Tests
def test_user_isolation(client, setup_data):
    owner_headers = setup_data["owner_headers"]
    user_headers = setup_data["user_headers"]
    other_headers = setup_data["other_headers"]

    # Create opp for owner
    c_owner = client.post("/api/customers", headers=owner_headers, json={"name": "Owner Cust"}).json()
    opp_owner = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": c_owner["id"], "title": "Owner Opp"}).json()

    # 1. USER가 다른 USER(또는 OWNER) Opportunity GET -> 실패
    res = client.get(f"/api/opportunities/{opp_owner['id']}", headers=user_headers)
    assert res.status_code == 403

    # 2. USER가 다른 USER Opportunity PATCH -> 실패
    res = client.patch(f"/api/opportunities/{opp_owner['id']}", headers=user_headers, json={"title": "Hack"})
    assert res.status_code == 403

    # 3. USER가 list query에 다른 assigned_user_id를 넣어도 타인 데이터 노출 없음
    c_user = client.post("/api/customers", headers=user_headers, json={"name": "User Cust"}).json()
    client.post("/api/opportunities", headers=user_headers, json={"customer_id": c_user["id"], "title": "User Opp"})
    
    res = client.get(f"/api/opportunities?assigned_user_id={setup_data['owner'].id}", headers=user_headers)
    assert len(res.json()) == 1
    assert res.json()[0]["assigned_user_id"] == setup_data["user1"].id

    # 4. USER가 다른 Company Opportunity 접근 -> 실패
    res = client.get(f"/api/opportunities/{opp_owner['id']}", headers=other_headers)
    assert res.status_code in [403, 404]

# 9. Customer / Tenant Tests
def test_customer_tenant_isolation(client, setup_data):
    user_headers = setup_data["user_headers"]
    other_headers = setup_data["other_headers"]
    owner_headers = setup_data["owner_headers"]

    c1 = client.post("/api/customers", headers=user_headers, json={"name": "C1"}).json()
    c2 = client.post("/api/customers", headers=other_headers, json={"name": "C2"}).json()

    # 1. 다른 Company Customer로 Opportunity 생성 실패
    res = client.post("/api/opportunities", headers=user_headers, json={"customer_id": c2["id"], "title": "Hack"})
    assert res.status_code in [403, 404]

    # 2. 같은 Company라도 USER가 접근 권한 없는 Customer이면 생성 실패
    c3 = client.post("/api/customers", headers=owner_headers, json={"name": "C3"}).json()
    res = client.post("/api/opportunities", headers=user_headers, json={"customer_id": c3["id"], "title": "Hack"})
    assert res.status_code in [403, 404]

    # 3. OWNER는 같은 Company Customer에 생성 가능
    res = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": c1["id"], "title": "Owner on User Cust"})
    assert res.status_code == 201

# 10. DELETE Tests
def test_delete_ownership(client, setup_data):
    owner_headers = setup_data["owner_headers"]
    user_headers = setup_data["user_headers"]
    other_headers = setup_data["other_headers"]

    customer = client.post("/api/customers", headers=owner_headers, json={"name": "Del Cust"}).json()
    opp = client.post("/api/opportunities", headers=owner_headers, json={"customer_id": customer["id"], "title": "Del Opp"}).json()
    oid = opp["id"]

    # Cross-Tenant -> tenant isolation 실패 (403 or 404 before 409)
    res = client.delete(f"/api/opportunities/{oid}", headers=other_headers)
    assert res.status_code in [403, 404]

    # 다른 USER -> ownership 실패
    res = client.delete(f"/api/opportunities/{oid}", headers=user_headers)
    assert res.status_code in [403, 404]

    # 권한 있는 자 -> 409
    res = client.delete(f"/api/opportunities/{oid}", headers=owner_headers)
    assert res.status_code == 409

# 11. Lifecycle Tests
def test_lifecycle_rules(client, setup_data):
    owner_headers = setup_data["owner_headers"]
    user_headers = setup_data["user_headers"]

    customer = client.post("/api/customers", headers=user_headers, json={"name": "LC Cust"}).json()
    
    # Create -> NEW 강제
    res = client.post("/api/opportunities", headers=user_headers, json={"customer_id": customer["id"], "title": "LC", "status": "WON"})
    assert res.status_code == 201
    assert res.json()["status"] == "NEW"
    oid = res.json()["id"]

    # Normal transitions
    for status in ["QUOTING", "NEGOTIATING", "ON_HOLD", "QUOTING", "WON"]:
        res = client.patch(f"/api/opportunities/{oid}", headers=user_headers, json={"status": status})
        assert res.status_code == 200

    # WON -> NEW (USER 불가)
    res = client.patch(f"/api/opportunities/{oid}", headers=user_headers, json={"status": "NEW"})
    assert res.status_code == 403

    # WON -> QUOTING (OWNER 가능)
    res = client.patch(f"/api/opportunities/{oid}", headers=owner_headers, json={"status": "QUOTING"})
    assert res.status_code == 200

    client.patch(f"/api/opportunities/{oid}", headers=user_headers, json={"status": "LOST"})
    
    # LOST -> QUOTING (USER 불가)
    res = client.patch(f"/api/opportunities/{oid}", headers=user_headers, json={"status": "QUOTING"})
    assert res.status_code == 403

    # LOST -> NEW (OWNER 가능)
    res = client.patch(f"/api/opportunities/{oid}", headers=owner_headers, json={"status": "NEW"})
    assert res.status_code == 200

# 12. Multi-Opportunity Tests
def test_multi_opportunity(client, setup_data):
    user_headers = setup_data["user_headers"]
    customer = client.post("/api/customers", headers=user_headers, json={"name": "Multi Cust"}).json()
    cid = customer["id"]

    opp_a = client.post("/api/opportunities", headers=user_headers, json={"customer_id": cid, "title": "Opp A"}).json()
    opp_b = client.post("/api/opportunities", headers=user_headers, json={"customer_id": cid, "title": "Opp B"}).json()

    client.patch(f"/api/opportunities/{opp_a['id']}", headers=user_headers, json={"status": "WON"})
    client.patch(f"/api/opportunities/{opp_b['id']}", headers=user_headers, json={"status": "QUOTING"})

    # Check independence
    res = client.get(f"/api/customers/{cid}/opportunities", headers=user_headers).json()
    assert len(res) == 2
    for r in res:
        if r["id"] == opp_a["id"]:
            assert r["status"] == "WON"
        elif r["id"] == opp_b["id"]:
            assert r["status"] == "QUOTING"

# 13. Contract 보유 Customer 테스트
def test_opportunity_for_contracted_customer(client, setup_data):
    user_headers = setup_data["user_headers"]
    customer = client.post("/api/customers", headers=user_headers, json={"name": "Contract Cust"}).json()
    cid = customer["id"]

    client.post("/api/contracts", headers=user_headers, json={"customer_id": cid, "vehicle_model": "Avante"})
    
    # Opportunity 생성 성공 확인
    res = client.post("/api/opportunities", headers=user_headers, json={"customer_id": cid, "title": "New Opp"})
    assert res.status_code == 201
