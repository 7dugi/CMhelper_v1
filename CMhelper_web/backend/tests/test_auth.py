import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure env vars are set before importing main
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["CMHELPER_INVITE_CODE"] = "TEST-INVITE"
os.environ["CMHELPER_OWNER_EMAIL"] = "owner@test.com"
os.environ["CMHELPER_DEFAULT_COMPANY_NAME"] = "Test Company"
os.environ["CMHELPER_DEFAULT_COMPANY_SLUG"] = "test-company"

from app.main import app
from app.database import Base, get_db

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

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_register_success():
    res = client.post("/api/auth/register", json={
        "name": "Owner User",
        "email": "owner@TEST.com",  # Test lowercase normalization
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "owner@test.com"
    assert data["role"] == "OWNER"

def test_register_duplicate_email():
    payload = {
        "name": "Test User",
        "email": "user@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    }
    client.post("/api/auth/register", json=payload)
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 409

def test_register_invalid_invite_code():
    res = client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "user2@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "WRONG-CODE"
    })
    assert res.status_code == 403

def test_login_success():
    client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "login@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    res = client.post("/api/auth/login", json={
        "email": "LOGIN@test.com", # Test lowercase normalization
        "password": "password123"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_password():
    client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "login2@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    res = client.post("/api/auth/login", json={
        "email": "login2@test.com",
        "password": "wrongpassword"
    })
    assert res.status_code == 401
    assert "Invalid credentials" in res.json()["detail"]

def test_auth_me():
    client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "me@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    login_res = client.post("/api/auth/login", json={
        "email": "me@test.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "me@test.com"

def test_auth_me_invalid_token():
    me_res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token"})
    assert me_res.status_code == 401

def test_register_email_trimming():
    res = client.post("/api/auth/register", json={
        "name": "Trim User",
        "email": "   trim@test.com   ",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    assert res.status_code == 201
    assert res.json()["email"] == "trim@test.com"

def test_register_email_case_insensitivity():
    client.post("/api/auth/register", json={
        "name": "Case User 1",
        "email": "case@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    res = client.post("/api/auth/register", json={
        "name": "Case User 2",
        "email": "CASE@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    assert res.status_code == 409

def test_register_password_too_short():
    res = client.post("/api/auth/register", json={
        "name": "Short Pass",
        "email": "short@test.com",
        "password": "pass",
        "password_confirm": "pass",
        "invite_code": "TEST-INVITE"
    })
    assert res.status_code == 422

def test_register_password_mismatch():
    res = client.post("/api/auth/register", json={
        "name": "Mismatch Pass",
        "email": "mismatch@test.com",
        "password": "password123",
        "password_confirm": "password456",
        "invite_code": "TEST-INVITE"
    })
    assert res.status_code == 422

def test_login_invalid_email_and_password_responses_are_identical():
    # Login with non-existent email
    res1 = client.post("/api/auth/login", json={
        "email": "nonexistent@test.com",
        "password": "password123"
    })
    # Login with wrong password for existing user
    client.post("/api/auth/register", json={
        "name": "Existent",
        "email": "existent@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    res2 = client.post("/api/auth/login", json={
        "email": "existent@test.com",
        "password": "wrongpassword"
    })
    assert res1.status_code == 401
    assert res2.status_code == 401
    assert res1.json()["detail"] == res2.json()["detail"] == "Invalid credentials"

def test_auth_me_expired_token():
    import time
    from app.main import create_access_token
    # manually create an expired token
    token = create_access_token({"sub": "999"})
    # hack to expire it immediately by replacing time
    import jwt
    from app.main import JWT_SECRET_KEY, JWT_ALGORITHM
    expired_token = jwt.encode({"sub": "999", "exp": int(time.time()) - 100}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401

def test_auth_me_inactive_user():
    res_reg = client.post("/api/auth/register", json={
        "name": "Inactive User",
        "email": "inactive@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    user_id = res_reg.json()["id"]
    
    # login to get token
    res_login = client.post("/api/auth/login", json={
        "email": "inactive@test.com",
        "password": "password123"
    })
    token = res_login.json()["access_token"]
    
    # manually deactivate user
    db = next(override_get_db())
    from app.models import User
    user = db.query(User).filter_by(id=user_id).first()
    user.status = "INACTIVE"
    db.commit()
    
    # token should now fail
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 403

def test_auth_me_inactive_company():
    res_reg = client.post("/api/auth/register", json={
        "name": "Inactive Co User",
        "email": "inactive_co@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    user_id = res_reg.json()["id"]
    
    res_login = client.post("/api/auth/login", json={
        "email": "inactive_co@test.com",
        "password": "password123"
    })
    token = res_login.json()["access_token"]
    
    # manually deactivate company
    db = next(override_get_db())
    from app.models import User, Company
    user = db.query(User).filter_by(id=user_id).first()
    company = db.query(Company).filter_by(id=user.company_id).first()
    company.status = "INACTIVE"
    db.commit()
    
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 403

def test_default_company_creation():
    db = next(override_get_db())
    from app.models import Company
    count_before = db.query(Company).count()
    client.post("/api/auth/register", json={
        "name": "Company User 1",
        "email": "co1@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    count_after_first = db.query(Company).count()
    
    client.post("/api/auth/register", json={
        "name": "Company User 2",
        "email": "co2@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    count_after_second = db.query(Company).count()
    
    # Only 1 new company should be created, and the second user should reuse it
    assert count_after_first == count_before + 1
    assert count_after_second == count_after_first

def test_missing_env_vars_fail_fast():
    import importlib
    import os
    import app.main
    # Remove a required env var
    original = os.environ.get("JWT_SECRET_KEY")
    del os.environ["JWT_SECRET_KEY"]
    try:
        with pytest.raises(RuntimeError) as exc_info:
            importlib.reload(app.main)
        assert "Fail-Fast" in str(exc_info.value)
    finally:
        os.environ["JWT_SECRET_KEY"] = original
        importlib.reload(app.main) # restore

def test_password_confirm_not_in_db():
    res = client.post("/api/auth/register", json={
        "name": "No Confirm",
        "email": "noconfirm@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    user_id = res.json()["id"]
    db = next(override_get_db())
    from app.models import User
    user = db.query(User).filter_by(id=user_id).first()
    assert not hasattr(user, "password_confirm")

def test_jwt_expiry_120_minutes():
    res_reg = client.post("/api/auth/register", json={
        "name": "JWT User",
        "email": "jwt@test.com",
        "password": "password123",
        "password_confirm": "password123",
        "invite_code": "TEST-INVITE"
    })
    res_login = client.post("/api/auth/login", json={
        "email": "jwt@test.com",
        "password": "password123"
    })
    token = res_login.json()["access_token"]
    
    import jwt
    from app.main import JWT_SECRET_KEY, JWT_ALGORITHM
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    
    # The difference between exp and iat should be exactly 120 minutes
    assert payload["exp"] - payload["iat"] == 120 * 60
