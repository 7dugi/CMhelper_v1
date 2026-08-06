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
