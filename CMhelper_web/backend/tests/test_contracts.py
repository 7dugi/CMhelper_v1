import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app import models, schemas, crud

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

@pytest.fixture(scope="function", autouse=True)
def clean_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    app.dependency_overrides.clear()
    
@pytest.fixture(scope="function")
def db_session():
    db = TestingSessionLocal()
    yield db
    db.close()

def get_auth_headers(user: models.User):
    from app.main import create_access_token
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )
    return {"Authorization": f"Bearer {access_token}"}

def test_contract_foundation(db_session: Session):
    db = db_session
    # Create two companies
    company1 = models.Company(name="Tenant A", slug="tenant-a")
    company2 = models.Company(name="Tenant B", slug="tenant-b")
    db.add_all([company1, company2])
    db.commit()

    # Create users in Tenant A
    owner_a = models.User(company_id=company1.id, name="Owner A", email="ownera@test.com", password_hash="hash", role="OWNER", status="ACTIVE")
    user_a1 = models.User(company_id=company1.id, name="User A1", email="usera1@test.com", password_hash="hash", role="USER", status="ACTIVE")
    user_a2 = models.User(company_id=company1.id, name="User A2", email="usera2@test.com", password_hash="hash", role="USER", status="ACTIVE")
    
    # Create users in Tenant B
    owner_b = models.User(company_id=company2.id, name="Owner B", email="ownerb@test.com", password_hash="hash", role="OWNER", status="ACTIVE")
    db.add_all([owner_a, user_a1, user_a2, owner_b])
    db.commit()
    db.refresh(owner_a)
    db.refresh(user_a1)
    db.refresh(user_a2)
    db.refresh(owner_b)

    # Create customers
    cust_a1 = models.Customer(company_id=company1.id, assigned_user_id=user_a1.id, name="Cust A1")
    cust_a2 = models.Customer(company_id=company1.id, assigned_user_id=user_a2.id, name="Cust A2")
    cust_b = models.Customer(company_id=company2.id, assigned_user_id=owner_b.id, name="Cust B")
    db.add_all([cust_a1, cust_a2, cust_b])
    db.commit()
    db.refresh(cust_a1)
    db.refresh(cust_a2)
    db.refresh(cust_b)

    headers_owner_a = get_auth_headers(owner_a)
    headers_user_a1 = get_auth_headers(user_a1)
    headers_user_a2 = get_auth_headers(user_a2)
    headers_owner_b = get_auth_headers(owner_b)

    # 1. USER own customer contract create PASS & 8. Contract assigned_user fallback works
    res = client.post("/api/contracts", json={
        "customer_id": cust_a1.id,
        "vehicle_model": "Tesla Model S"
    }, headers=headers_user_a1)
    assert res.status_code == 201
    contract1 = res.json()
    assert contract1["vehicle_model"] == "Tesla Model S"
    assert contract1["assigned_user_id"] == user_a1.id

    # 2. USER own contract list PASS
    res = client.get("/api/contracts", headers=headers_user_a1)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == contract1["id"]

    # 3. USER same-company other user's customer contract create BLOCK
    res = client.post("/api/contracts", json={
        "customer_id": cust_a2.id,
        "vehicle_model": "Blocked Car"
    }, headers=headers_user_a1)
    assert res.status_code == 404

    # 4. USER cross-company customer contract create BLOCK
    res = client.post("/api/contracts", json={
        "customer_id": cust_b.id,
        "vehicle_model": "Blocked Car"
    }, headers=headers_user_a1)
    assert res.status_code == 404

    # 5. OWNER same-company other user's contract create PASS
    res = client.post("/api/contracts", json={
        "customer_id": cust_a2.id,
        "vehicle_model": "Owner Created Car"
    }, headers=headers_owner_a)
    assert res.status_code == 201
    contract2 = res.json()
    assert contract2["assigned_user_id"] == user_a2.id

    # 6. OWNER all-company own tenant contracts list PASS
    res = client.get("/api/contracts?scope=all", headers=headers_owner_a)
    assert res.status_code == 200
    contracts_list = res.json()
    assert len(contracts_list) == 2

    # 7. OWNER cross-company contract access BLOCK
    res = client.get(f"/api/contracts/{contract1['id']}", headers=headers_owner_b)
    assert res.status_code == 403

    # 9. assigned_user override OWNER only
    res = client.patch(f"/api/contracts/{contract1['id']}", json={
        "assigned_user_id": user_a2.id
    }, headers=headers_user_a1)
    assert res.status_code == 403

    res = client.patch(f"/api/contracts/{contract1['id']}", json={
        "assigned_user_id": user_a2.id
    }, headers=headers_owner_a)
    assert res.status_code == 200
    assert res.json()["assigned_user_id"] == user_a2.id

    # 10. Customer -> contracts relationship works
    cust_a1_refreshed = crud.get_customer(db, cust_a1.id)
    assert len(cust_a1_refreshed.contracts) == 1
    assert cust_a1_refreshed.contracts[0].id == contract1["id"]

    # 11. legacy_origin_customer_id uniqueness works locally
    c_legacy = models.Contract(company_id=company1.id, customer_id=cust_a1.id, assigned_user_id=owner_a.id, legacy_origin_customer_id=999)
    db.add(c_legacy)
    db.commit()

    c_legacy_dup = models.Contract(company_id=company1.id, customer_id=cust_a2.id, assigned_user_id=owner_a.id, legacy_origin_customer_id=999)
    db.add(c_legacy_dup)
    try:
        db.commit()
        assert False, "Should have raised IntegrityError"
    except Exception as e:
        db.rollback()
        assert "unique constraint failed" in str(e).lower() or "unique index" in str(e).lower() or "duplicate key" in str(e).lower()
