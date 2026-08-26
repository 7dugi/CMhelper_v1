import os
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["CMHELPER_INVITE_CODE"] = "TEST-INVITE"
os.environ["CMHELPER_OWNER_EMAIL"] = "owner@test.com"
os.environ["CMHELPER_DEFAULT_COMPANY_NAME"] = "Test Company"
os.environ["CMHELPER_DEFAULT_COMPANY_SLUG"] = "test-company"

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import IntegrityError

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app, create_access_token, run_migrations
from app.database import Base, get_db
from app.models import User, Company, Customer, Opportunity, Quote, Contract, UserRole, UserStatus, CompanyStatus


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    
    db = TestingSessionLocal()
    try:
        # Create companies
        c1 = Company(name="Test Co", slug="test-co", status=CompanyStatus.ACTIVE.value)
        c2 = Company(name="Other Co", slug="other-co", status=CompanyStatus.ACTIVE.value)
        db.add_all([c1, c2])
        db.commit()
        db.refresh(c1)
        db.refresh(c2)

        # Create users
        u1 = User(email="owner1@test.com", password_hash="pw", name="O1", role=UserRole.OWNER.value, company_id=c1.id, status=UserStatus.ACTIVE.value)
        u2 = User(email="user1@test.com", password_hash="pw", name="U1", role=UserRole.USER.value, company_id=c1.id, status=UserStatus.ACTIVE.value)
        u3 = User(email="user2@test.com", password_hash="pw", name="U2", role=UserRole.USER.value, company_id=c1.id, status=UserStatus.ACTIVE.value)
        u4 = User(email="owner2@test.com", password_hash="pw", name="O2", role=UserRole.OWNER.value, company_id=c2.id, status=UserStatus.ACTIVE.value)
        db.add_all([u1, u2, u3, u4])
        db.commit()

        # Create customers
        cust1 = Customer(name="Cust1", contact="010-1111", company_id=c1.id, assigned_user_id=u1.id)
        cust2 = Customer(name="Cust2", contact="010-2222", company_id=c2.id, assigned_user_id=u4.id)
        db.add_all([cust1, cust2])
        db.commit()
    finally:
        db.close()

    yield

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)

def get_token(user_id: int) -> str:
    return create_access_token(data={"sub": str(user_id)})

def _get_test_entities(db):
    c1 = db.query(Company).filter_by(slug="test-co").first()
    c2 = db.query(Company).filter_by(slug="other-co").first()
    u1 = db.query(User).filter_by(email="owner1@test.com").first()
    u2 = db.query(User).filter_by(email="user1@test.com").first()
    u3 = db.query(User).filter_by(email="user2@test.com").first()
    u4 = db.query(User).filter_by(email="owner2@test.com").first()
    cust1 = db.query(Customer).filter_by(name="Cust1").first()
    cust2 = db.query(Customer).filter_by(name="Cust2").first()
    return c1, c2, u1, u2, u3, u4, cust1, cust2


def test_conversion_success():
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp1")
        db.add(opp)
        db.commit()
        db.refresh(opp)

        quote = Quote(company_id=c1.id, opportunity_id=opp.id, assigned_user_id=u2.id, vehicle_name="Car", product_type="LEASE", capital_company="Lotte", term_months=48, monthly_payment=500000)
        db.add(quote)
        db.commit()
        db.refresh(quote)
        opp_id = opp.id
        quote_id = quote.id
        cust_id = opp.customer_id
        u2_id = u2.id
    finally:
        db.close()

    token = get_token(u2_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={
        "source_quote_id": quote_id,
        "vehicle_model": "Car",
        "monthly_payment": 500000
    })
    
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_opportunity_id"] == opp_id
    assert data["source_quote_id"] == quote_id
    assert data["monthly_payment"] == 500000
    assert data["customer_id"] == cust_id
    assert data["assigned_user_id"] == u2_id # USER is forced to self


def test_duplicate_conversion():
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp2")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()

    token = get_token(u2_id)
    payload = {"vehicle_model": "Car"}
    # First conversion
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp.status_code == 201
    
    # Second conversion (duplicate)
    resp2 = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["detail"] == "Opportunity already converted"


def test_db_unique_integrity_error_mapped_to_409():
    """Verify that a database IntegrityError on source_opportunity_id is caught and mapped to HTTP 409."""
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp_Race")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()

    token = get_token(u2_id)
    payload = {"vehicle_model": "Car"}

    # Simulate race condition where application-level check passes but commit raises IntegrityError
    with patch("sqlalchemy.orm.Session.commit") as mock_commit:
        mock_commit.side_effect = IntegrityError(
            "statement",
            {},
            Exception("UNIQUE constraint failed: contracts.source_opportunity_id")
        )
        resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Opportunity already converted"


def test_db_pg_unique_integrity_error_mapped_to_409():
    """Verify PostgreSQL diagnostic constraint name mapping to HTTP 409."""
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp_Pg_Race")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()

    token = get_token(u2_id)
    payload = {"vehicle_model": "Car"}

    mock_orig = MagicMock()
    mock_orig.diag.constraint_name = "uq_contracts_source_opportunity_id"

    with patch("sqlalchemy.orm.Session.commit") as mock_commit:
        mock_commit.side_effect = IntegrityError("statement", {}, mock_orig)
        resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Opportunity already converted"


def test_db_pg_unrelated_integrity_error_returns_400():
    """Verify PostgreSQL unrelated diagnostic constraint returns HTTP 400."""
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp_Pg_Other")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()

    token = get_token(u2_id)
    payload = {"vehicle_model": "Car"}

    mock_orig = MagicMock()
    mock_orig.diag.constraint_name = "fk_contracts_source_quote_id"

    with patch("sqlalchemy.orm.Session.commit") as mock_commit:
        mock_commit.side_effect = IntegrityError("statement", {}, mock_orig)
        resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Database integrity constraint violation"


def test_db_unrelated_integrity_error_returns_400():
    """Verify that unrelated database IntegrityErrors return HTTP 400 without exposing DB internals."""
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp_Err")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()

    token = get_token(u2_id)
    payload = {"vehicle_model": "Car"}

    with patch("sqlalchemy.orm.Session.commit") as mock_commit:
        mock_commit.side_effect = IntegrityError(
            "statement",
            {},
            Exception("NOT NULL constraint failed: contracts.customer_id")
        )
        resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Database integrity constraint violation"


def test_db_unrelated_unique_integrity_error_returns_400():
    """Verify that unrelated SQLite unique constraint errors return HTTP 400."""
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp_Err_Uq")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()

    token = get_token(u2_id)
    payload = {"vehicle_model": "Car"}

    with patch("sqlalchemy.orm.Session.commit") as mock_commit:
        mock_commit.side_effect = IntegrityError(
            "statement",
            {},
            Exception("UNIQUE constraint failed: contracts.legacy_origin_customer_id")
        )
        resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Database integrity constraint violation"


def test_not_won():
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="QUOTING", title="Opp3")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()

    token = get_token(u2_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"vehicle_model": "Car"})
    assert resp.status_code == 400


def test_cross_tenant_isolation():
    db = TestingSessionLocal()
    try:
        c1, _, u1, _, _, u4, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u1.id, status="WON", title="Opp4")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u4_id = u4.id
    finally:
        db.close()

    # user from company 2 tries to convert company 1 opportunity
    token = get_token(u4_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"vehicle_model": "Car"})
    assert resp.status_code == 404


def test_user_wrong_assignment():
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, u3, _, cust1, _ = _get_test_entities(db)
        # assigned to u3
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u3.id, status="WON", title="Opp5")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()

    # u2 tries to convert
    token = get_token(u2_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"vehicle_model": "Car"})
    assert resp.status_code == 403


def test_owner_can_assign_other():
    db = TestingSessionLocal()
    try:
        c1, _, u1, u2, u3, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp6")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u1_id = u1.id
        u3_id = u3.id
    finally:
        db.close()

    # owner u1 converts and assigns to u3
    token = get_token(u1_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={
        "assigned_user_id": u3_id,
        "vehicle_model": "Car"
    })
    assert resp.status_code == 201
    assert resp.json()["assigned_user_id"] == u3_id


def test_wrong_quote_relation():
    db = TestingSessionLocal()
    try:
        c1, _, u1, _, _, _, cust1, _ = _get_test_entities(db)
        opp1 = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u1.id, status="WON", title="Opp7")
        opp2 = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u1.id, status="WON", title="Opp8")
        db.add_all([opp1, opp2])
        db.commit()
        db.refresh(opp1)
        db.refresh(opp2)

        # quote belongs to opp2
        quote = Quote(company_id=c1.id, opportunity_id=opp2.id, assigned_user_id=u1.id, product_type="LEASE", vehicle_name="Car")
        db.add(quote)
        db.commit()
        db.refresh(quote)
        opp1_id = opp1.id
        quote_id = quote.id
        u1_id = u1.id
    finally:
        db.close()

    token = get_token(u1_id)
    # try converting opp1 using quote from opp2
    resp = client.post(f"/api/opportunities/{opp1_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={
        "source_quote_id": quote_id
    })
    assert resp.status_code == 404


def test_conversion_success_no_quote():
    db = TestingSessionLocal()
    try:
        c1, _, u1, _, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u1.id, status="WON", title="Opp_no_quote")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        cust_id = opp.customer_id
        u1_id = u1.id
    finally:
        db.close()

    token = get_token(u1_id)
    payload = {"vehicle_model": "Car2"}
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_opportunity_id"] == opp_id
    assert data["source_quote_id"] is None
    assert data["customer_id"] == cust_id


def test_cross_tenant_quote():
    db = TestingSessionLocal()
    try:
        c1, c2, u1, _, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u1.id, status="WON", title="Opp_cross_quote")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id

        # quote from company 2
        quote = Quote(company_id=c2.id, opportunity_id=opp_id, assigned_user_id=u1.id, product_type="LEASE", vehicle_name="Car")
        db.add(quote)
        db.commit()
        db.refresh(quote)
        quote_id = quote.id
        u1_id = u1.id
    finally:
        db.close()

    token = get_token(u1_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"source_quote_id": quote_id})
    assert resp.status_code == 404


def test_user_cannot_reassign():
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, u3, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="WON", title="Opp_reassign")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
        u3_id = u3.id
    finally:
        db.close()

    token = get_token(u2_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"assigned_user_id": u3_id})
    assert resp.status_code == 201
    assert resp.json()["assigned_user_id"] == u2_id


def test_owner_assign_cross_tenant():
    db = TestingSessionLocal()
    try:
        c1, _, u1, _, _, u4, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u1.id, status="WON", title="Opp_owner_assign")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u1_id = u1.id
        u4_id = u4.id
    finally:
        db.close()

    token = get_token(u1_id) # owner of company 1
    # User 4 is company 2
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"assigned_user_id": u4_id})
    assert resp.status_code == 400
    assert "Invalid assigned_user_id" in resp.json()["detail"]


def test_owner_assign_inactive():
    db = TestingSessionLocal()
    try:
        c1, _, u1, _, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u1.id, status="WON", title="Opp_inactive")
        db.add(opp)
        # create inactive user in company 1
        u = User(company_id=c1.id, email="inactive@a.com", name="I", password_hash="pw", role="USER", status="INACTIVE")
        db.add(u)
        db.commit()
        db.refresh(opp)
        db.refresh(u)
        opp_id = opp.id
        u_id = u.id
        u1_id = u1.id
    finally:
        db.close()

    token = get_token(u1_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"assigned_user_id": u_id})
    assert resp.status_code == 400


def test_not_won_new():
    db = TestingSessionLocal()
    try:
        c1, _, _, u2, _, _, cust1, _ = _get_test_entities(db)
        opp = Opportunity(company_id=c1.id, customer_id=cust1.id, assigned_user_id=u2.id, status="NEW", title="Opp3_new")
        db.add(opp)
        db.commit()
        db.refresh(opp)
        opp_id = opp.id
        u2_id = u2.id
    finally:
        db.close()
    token = get_token(u2_id)
    resp = client.post(f"/api/opportunities/{opp_id}/convert-to-contract", headers={"Authorization": f"Bearer {token}"}, json={"vehicle_model": "Car"})
    assert resp.status_code == 400
