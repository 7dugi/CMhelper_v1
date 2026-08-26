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
import datetime

from app.database import Base, get_db
from app.main import app
from app import models, crud, schemas

# Set up test DB (SQLite in-memory)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # 1. Company
    c = models.Company(name="Test Company", slug="testco")
    db.add(c)
    db.commit()
    
    # 2. Users
    owner = models.User(company_id=c.id, email="owner@test.com", password_hash="hash", name="Owner", role="OWNER", status="ACTIVE")
    user1 = models.User(company_id=c.id, email="u1@test.com", password_hash="hash", name="User1", role="USER", status="ACTIVE")
    db.add(owner)
    db.add(user1)
    db.commit()
    
    today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    d30_str = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    d90_str = (datetime.datetime.utcnow() + datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    d120_str = (datetime.datetime.utcnow() + datetime.timedelta(days=120)).strftime("%Y-%m-%d")
    past_str = (datetime.datetime.utcnow() - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
    future_str = (datetime.datetime.utcnow() + datetime.timedelta(days=400)).strftime("%Y-%m-%d")

    # 3. Customer 1: no contracts
    cust1 = models.Customer(company_id=c.id, assigned_user_id=user1.id, name="Cust1 No Contract")
    # 4. Customer 2: one active contract
    cust2 = models.Customer(company_id=c.id, assigned_user_id=user1.id, name="Cust2 One Contract")
    # 5. Customer 3: multiple contracts (past, d30, d90)
    cust3 = models.Customer(company_id=c.id, assigned_user_id=user1.id, name="Cust3 Multiple")
    # 6. Customer 4: only expired contracts
    cust4 = models.Customer(company_id=c.id, assigned_user_id=user1.id, name="Cust4 Expired")
    # 7. Customer 5: today, d30, past
    cust5 = models.Customer(company_id=c.id, assigned_user_id=user1.id, name="Cust5 Today")
    # 8. Customer 6: exact d90, d120
    cust6 = models.Customer(company_id=c.id, assigned_user_id=user1.id, name="Cust6 Exact D90")
    
    db.add_all([cust1, cust2, cust3, cust4, cust5, cust6])
    db.commit()

    # Add contracts
    cont2 = models.Contract(company_id=c.id, customer_id=cust2.id, assigned_user_id=user1.id, expiry_date=d30_str)
    
    cont3_1 = models.Contract(company_id=c.id, customer_id=cust3.id, assigned_user_id=user1.id, expiry_date=past_str)
    cont3_2 = models.Contract(company_id=c.id, customer_id=cust3.id, assigned_user_id=user1.id, expiry_date=d30_str)
    cont3_3 = models.Contract(company_id=c.id, customer_id=cust3.id, assigned_user_id=user1.id, expiry_date=d90_str)
    
    cont4_1 = models.Contract(company_id=c.id, customer_id=cust4.id, assigned_user_id=user1.id, expiry_date=past_str)
    cont4_2 = models.Contract(company_id=c.id, customer_id=cust4.id, assigned_user_id=user1.id, expiry_date=past_str)

    cont5_1 = models.Contract(company_id=c.id, customer_id=cust5.id, assigned_user_id=user1.id, expiry_date=past_str)
    cont5_2 = models.Contract(company_id=c.id, customer_id=cust5.id, assigned_user_id=user1.id, expiry_date=today_str)
    cont5_3 = models.Contract(company_id=c.id, customer_id=cust5.id, assigned_user_id=user1.id, expiry_date=d30_str)
    
    cont6_1 = models.Contract(company_id=c.id, customer_id=cust6.id, assigned_user_id=user1.id, expiry_date=d90_str)
    cont6_2 = models.Contract(company_id=c.id, customer_id=cust6.id, assigned_user_id=user1.id, expiry_date=d120_str)

    db.add_all([cont2, cont3_1, cont3_2, cont3_3, cont4_1, cont4_2, cont5_1, cont5_2, cont5_3, cont6_1, cont6_2])
    db.commit()

    yield {
        "db": db,
        "company_id": c.id,
        "user_id": user1.id,
        "c1": cust1.id,
        "c2": cust2.id,
        "c3": cust3.id,
        "c4": cust4.id,
        "c5": cust5.id,
        "c6": cust6.id,
        "today": today_str,
        "d30": d30_str,
        "d90": d90_str,
        "d120": d120_str,
        "past": past_str,
    }
    
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_list_customers_aggregation_and_n_plus_one(setup_db):
    db = setup_db["db"]
    company_id = setup_db["company_id"]
    
    # Trace N+1 using sqlalchemy events
    from sqlalchemy import event
    query_count = 0
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1
        
    event.listen(db.get_bind(), "before_cursor_execute", before_cursor_execute)
    
    customers = crud.list_customers(db, company_id=company_id)
    
    event.remove(db.get_bind(), "before_cursor_execute", before_cursor_execute)
    
    # 1. Ensure set-based execution (query_count should be exactly 2 because of joinedload assigned_user or just 1)
    # The count will not be proportional to the number of customers (6).
    assert query_count <= 3, f"Too many queries: {query_count}, implies N+1"

    c_map = {c.id: c for c in customers}
    
    c1 = c_map[setup_db["c1"]]
    assert c1.contract_count == 0
    assert c1.nearest_expiry is None

    c2 = c_map[setup_db["c2"]]
    assert c2.contract_count == 1
    assert c2.nearest_expiry == setup_db["d30"]
    
    c3 = c_map[setup_db["c3"]]
    assert c3.contract_count == 3
    # Should ignore the past_str, and pick d30_str as nearest among [past, d30, d90]
    assert c3.nearest_expiry == setup_db["d30"]

    c4 = c_map[setup_db["c4"]]
    assert c4.contract_count == 2
    # Since all are expired (past), no future expiry exists
    assert c4.nearest_expiry is None

    c5 = c_map[setup_db["c5"]]
    assert c5.contract_count == 3
    # Today should be included, so between past, today, d30 => today
    assert c5.nearest_expiry == setup_db["today"]

    c6 = c_map[setup_db["c6"]]
    assert c6.contract_count == 2
    # Between exact d90 and d120 => d90
    assert c6.nearest_expiry == setup_db["d90"]


def test_get_customer_aggregation(setup_db):
    db = setup_db["db"]
    
    c3 = crud.get_customer(db, setup_db["c3"])
    assert c3.contract_count == 3
    assert c3.nearest_expiry == setup_db["d30"]

    c4 = crud.get_customer(db, setup_db["c4"])
    assert c4.contract_count == 2
    assert c4.nearest_expiry is None

