import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from app import models, crud, schemas
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture(scope="module")
def db_session():
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture(scope="module")
def setup_test_users(db_session):
    # Setup test company
    company = crud.get_or_create_default_company(db_session, "Test Co", "test-co")
    
    # Clean up existing users for this company
    db_session.query(models.User).filter_by(company_id=company.id).delete()
    db_session.commit()

    # Create Owner
    owner = crud.create_user(db_session, schemas.UserCreate(email="owner@test.com", password="password", password_confirm="password", invite_code="CMH-DEFAULT-CODE", name="Owner", phone="010-0000-0000"), company_id=company.id, role=models.UserRole.OWNER.value, status=models.UserStatus.ACTIVE.value)
    
    # Create User A
    user_a = crud.create_user(db_session, schemas.UserCreate(email="usera@test.com", password="password", password_confirm="password", invite_code="CMH-DEFAULT-CODE", name="User A", phone="010-1111-1111"), company_id=company.id, role=models.UserRole.USER.value, status=models.UserStatus.ACTIVE.value)

    # Create User B
    user_b = crud.create_user(db_session, schemas.UserCreate(email="userb@test.com", password="password", password_confirm="password", invite_code="CMH-DEFAULT-CODE", name="User B", phone="010-2222-2222"), company_id=company.id, role=models.UserRole.USER.value, status=models.UserStatus.ACTIVE.value)

    return {"owner": owner, "user_a": user_a, "user_b": user_b, "company": company}

def get_token(email, password="password"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]

def test_ownership_isolation(setup_test_users):
    users = setup_test_users
    
    token_a = get_token("usera@test.com")
    token_b = get_token("userb@test.com")
    token_owner = get_token("owner@test.com")

    # 1. User A creates a customer
    res_a = client.post("/api/customers", 
        json={"name": "Customer A"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_a.status_code == 201
    cust_a_id = res_a.json()["id"]

    # 2. User B creates a customer
    res_b = client.post("/api/customers", 
        json={"name": "Customer B"},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b.status_code == 201
    cust_b_id = res_b.json()["id"]

    # 3. User A lists customers - should only see Customer A
    res_list_a = client.get("/api/customers", headers={"Authorization": f"Bearer {token_a}"})
    assert res_list_a.status_code == 200
    names_a = [c["name"] for c in res_list_a.json()]
    assert "Customer A" in names_a
    assert "Customer B" not in names_a

    # 4. User A tries to GET Customer B directly - should 404
    res_get_b_by_a = client.get(f"/api/customers/{cust_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_get_b_by_a.status_code == 404

    # 5. User A tries to UPDATE Customer B directly - should 404
    res_put_b_by_a = client.put(f"/api/customers/{cust_b_id}", json={"name": "Hacked"}, headers={"Authorization": f"Bearer {token_a}"})
    assert res_put_b_by_a.status_code == 404

    # 6. User A tries to DELETE Customer B directly - should 404
    res_del_b_by_a = client.delete(f"/api/customers/{cust_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_del_b_by_a.status_code == 404

    # 7. Owner lists customers - should see both with scope=all
    res_list_owner = client.get("/api/customers?scope=all", headers={"Authorization": f"Bearer {token_owner}"})
    assert res_list_owner.status_code == 200
    names_owner = [c["name"] for c in res_list_owner.json()]
    assert "Customer A" in names_owner
    assert "Customer B" in names_owner

    # 8. User B creates a consultation for Customer B
    res_cons_b = client.post(f"/api/customers/{cust_b_id}/consultations", 
        json={"notes": "Notes by B"},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_cons_b.status_code == 201
    cons_b_id = res_cons_b.json()["id"]

    # 9. User A tries to delete User B's consultation
    res_del_cons_b = client.delete(f"/api/consultations/{cons_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_del_cons_b.status_code == 404

    # 10. User B queues a message for Customer B
    res_msg_b = client.post("/api/messages/queue",
        json=[{"customer_id": cust_b_id, "message_text": "Hello B"}],
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_msg_b.status_code == 200

    # 11. User A tries to queue a message for Customer B
    res_msg_a = client.post("/api/messages/queue",
        json=[{"customer_id": cust_b_id, "message_text": "Hello B"}],
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_msg_a.status_code == 404

def test_customer_workspace_segmentation(setup_test_users):
    users = setup_test_users
    
    token_owner = get_token("owner@test.com")
    token_a = get_token("usera@test.com")
    token_b = get_token("userb@test.com")

    # Clear all customers for clean test
    db_session = TestingSessionLocal()
    db_session.query(models.Customer).delete()
    db_session.commit()
    db_session.close()

    # Create customers
    res = client.post("/api/customers", json={"name": "Owner Cust 1"}, headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 201
    res = client.post("/api/customers", json={"name": "Owner Cust 2"}, headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 201
    res = client.post("/api/customers", json={"name": "User A Cust 1"}, headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 201

    user_a_id = users["user_a"].id
    
    # OWNER default GET -> own only
    res = client.get("/api/customers", headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 200
    assert len(res.json()) == 2
    assert all(c["assigned_user_id"] == users["owner"].id for c in res.json())

    # OWNER scope=all -> company all
    res = client.get("/api/customers?scope=all", headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 200
    assert len(res.json()) == 3

    # OWNER assigned_user_id=USER_A -> USER_A only
    res = client.get(f"/api/customers?assigned_user_id={user_a_id}", headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "User A Cust 1"

    # OWNER assigned_user_id=OTHER_COMPANY -> 403 Forbidden
    res = client.get("/api/customers?assigned_user_id=9999", headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 403

    # USER default -> own only
    res = client.get("/api/customers", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "User A Cust 1"

    # USER scope=all -> 403 차단
    res = client.get("/api/customers?scope=all", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 403

    # USER assigned_user_id=OWNER -> 403 차단
    res = client.get(f"/api/customers?assigned_user_id={users['owner'].id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 403


def test_assigned_user_name_exposure(setup_test_users):
    users = setup_test_users
    token_owner = get_token("owner@test.com")
    token_a = get_token("usera@test.com")
    
    # A. OWNER 본인 고객 조회 시 assigned_user_name == OWNER.name
    res = client.get("/api/customers", headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 200
    for c in res.json():
        if c["name"].startswith("Owner Cust"):
            assert c["assigned_user_name"] == users["owner"].name

    # B. OWNER가 특정 USER workspace 조회 시 assigned_user_name == USER.name
    res = client.get(f"/api/customers?assigned_user_id={users['user_a'].id}", headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 200
    assert len(res.json()) > 0
    for c in res.json():
        assert c["assigned_user_name"] == users["user_a"].name

    # C. OWNER scope=all 조회 시 각 Customer의 담당자 매칭 검증
    res = client.get("/api/customers?scope=all", headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 200
    for c in res.json():
        if c["assigned_user_id"] == users["owner"].id:
            assert c["assigned_user_name"] == users["owner"].name
        elif c["assigned_user_id"] == users["user_a"].id:
            assert c["assigned_user_name"] == users["user_a"].name

    # D. USER가 자신의 고객 조회 시 정상 작동
    res = client.get("/api/customers", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    for c in res.json():
        assert c["assigned_user_name"] == users["user_a"].name

    # E. USER가 다른 USER workspace 강제 조회 차단
    res = client.get(f"/api/customers?assigned_user_id={users['user_b'].id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 403

    # F. 다른 Company 정보 노출 차단 (Tenant Isolation)
    res = client.get("/api/customers?assigned_user_id=9999", headers={"Authorization": f"Bearer {token_owner}"})
    assert res.status_code == 403

