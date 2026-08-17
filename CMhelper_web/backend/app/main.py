"""CMhelper v1 — FastAPI backend entry point"""
from __future__ import annotations

import io
import json
import csv
import openpyxl
from typing import List, Optional
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from . import crud, models, schemas


# ── DB bootstrap ───────────────────────────────────────────────────────────────


def run_migrations(eng) -> None:
    """Forward-only column migrations for SQLite and Postgres."""
    dialect = eng.dialect.name
    with eng.begin() as conn:
        if dialect == "sqlite":
            result = conn.execute(text("PRAGMA table_info(customers)"))
            existing_cust = {row[1] for row in result.fetchall()}
            result = conn.execute(text("PRAGMA table_info(field_definitions)"))
            existing_fd = {row[1] for row in result.fetchall()}
            result = conn.execute(text("PRAGMA table_info(message_tasks)"))
            existing_mt = {row[1] for row in result.fetchall()}
            result = conn.execute(text("PRAGMA table_info(contracts)"))
            existing_contracts = {row[1] for row in result.fetchall()}
        else:
            # PostgreSQL
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='customers'"))
            existing_cust = {row[0] for row in result.fetchall()}
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='field_definitions'"))
            existing_fd = {row[0] for row in result.fetchall()}
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='message_tasks'"))
            existing_mt = {row[0] for row in result.fetchall()}
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='contracts'"))
            existing_contracts = {row[0] for row in result.fetchall()}

        # Customers table
        cust_cols = [
            ("contact",         "VARCHAR",           "VARCHAR"),
            ("region",          "VARCHAR",           "VARCHAR"),
            ("contract_date",   "VARCHAR",           "VARCHAR"),
            ("contract_months", "INTEGER",           "INTEGER"),
            ("expiry_date",     "VARCHAR",           "VARCHAR"),
            ("capital",         "VARCHAR",           "VARCHAR"),
            ("product_type",    "VARCHAR",           "VARCHAR"),
            ("is_prospect",     "BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE"),
            ("is_contracted",   "BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE"),
            ("anniversary",     "VARCHAR",           "VARCHAR"),
            ("memo",            "VARCHAR",           "VARCHAR"),
            ("estimate_image",  "VARCHAR",           "VARCHAR"),
            ("sent_quotes",     "TEXT DEFAULT '[]'", "JSONB DEFAULT '[]'::jsonb"),
            ("extra",           "TEXT DEFAULT '{}'", "JSONB DEFAULT '{}'::jsonb"),
        ]
        for col_name, sqlite_type, pg_type in cust_cols:
            if col_name not in existing_cust:
                ctype = sqlite_type if dialect == "sqlite" else pg_type
                conn.execute(text(f"ALTER TABLE customers ADD COLUMN {col_name} {ctype}"))

        # FieldDefinitions table
        fd_cols = [
            ("target_type", "VARCHAR DEFAULT 'contracted'", "VARCHAR DEFAULT 'contracted'"),
        ]
        for col_name, sqlite_type, pg_type in fd_cols:
            if col_name not in existing_fd:
                ctype = sqlite_type if dialect == "sqlite" else pg_type
                conn.execute(text(f"ALTER TABLE field_definitions ADD COLUMN {col_name} {ctype}"))

        # MessageTasks table
        mt_cols = [
            ("scheduled_at", "DATETIME", "TIMESTAMP"),
        ]
        for col_name, sqlite_type, pg_type in mt_cols:
            if col_name not in existing_mt:
                ctype = sqlite_type if dialect == "sqlite" else pg_type
                conn.execute(text(f"ALTER TABLE message_tasks ADD COLUMN {col_name} {ctype}"))

        # Contracts table
        contract_cols = [
            ("source_opportunity_id", "INTEGER", "INTEGER"),
            ("source_quote_id", "INTEGER", "INTEGER"),
            ("monthly_payment", "BIGINT", "BIGINT"),
        ]
        for col_name, sqlite_type, pg_type in contract_cols:
            if col_name not in existing_contracts:
                ctype = sqlite_type if dialect == "sqlite" else pg_type
                conn.execute(text(f"ALTER TABLE contracts ADD COLUMN {col_name} {ctype}"))
                
        # Idempotent index creation
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_contracts_source_opportunity_id ON contracts(source_opportunity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contracts_source_quote_id ON contracts(source_quote_id)"))


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="CMhelper v1", version="1.0.0")

@app.on_event("startup")
def startup_event():
    # ── DB bootstrap ───────────────────────────────────────────────────────────────
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    
    # Seed default field definitions once
    _boot_db = next(get_db())
    try:
        crud.seed_defaults(_boot_db)
    finally:
        _boot_db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
import uuid
import shutil
import time
from dotenv import load_dotenv
from supabase import create_client, Client
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

# ── Auth Configuration & Fail-Fast ─────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
CMHELPER_INVITE_CODE = os.getenv("CMHELPER_INVITE_CODE")
CMHELPER_OWNER_EMAIL = os.getenv("CMHELPER_OWNER_EMAIL")
CMHELPER_DEFAULT_COMPANY_NAME = os.getenv("CMHELPER_DEFAULT_COMPANY_NAME")
CMHELPER_DEFAULT_COMPANY_SLUG = os.getenv("CMHELPER_DEFAULT_COMPANY_SLUG")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
JWT_ALGORITHM = "HS256"

if not all([JWT_SECRET_KEY, CMHELPER_INVITE_CODE, CMHELPER_OWNER_EMAIL, CMHELPER_DEFAULT_COMPANY_NAME, CMHELPER_DEFAULT_COMPANY_SLUG]):
    raise RuntimeError("Fail-Fast: 필수 인증 환경변수(JWT_SECRET_KEY, CMHELPER_INVITE_CODE 등)가 누락되었습니다. (.env 파일을 확인하세요)")

security = HTTPBearer()

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    now = int(time.time())
    expire = now + (JWT_EXPIRE_MINUTES * 60)
    to_encode.update({"iat": now, "exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    user = db.query(models.User).filter_by(id=int(user_id_str)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    if user.status != models.UserStatus.ACTIVE.value:
        raise HTTPException(status_code=403, detail="User is inactive")
        
    if user.company.status != models.CompanyStatus.ACTIVE.value:
        raise HTTPException(status_code=403, detail="Company is inactive")
        
    return user

def require_owner(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.OWNER.value:
        raise HTTPException(status_code=403, detail="Owner privileges required")
    return current_user

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

IS_VERCEL = (
    os.getenv("VERCEL") == "1" 
    or os.path.abspath(__file__).startswith("/var/task") 
    or "AWS_LAMBDA_FUNCTION_NAME" in os.environ
)
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")

if not IS_VERCEL:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    new_filename = f"{uuid.uuid4().hex}.{ext}"
    file_bytes = await file.read()

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            import urllib.request
            import urllib.error
            import json
            
            base_url = SUPABASE_URL.rstrip('/')
            upload_url = f"{base_url}/storage/v1/object/estimates/{new_filename}"
            headers = {
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "apikey": SUPABASE_KEY,
                "Content-Type": file.content_type or "application/octet-stream"
            }
            
            req = urllib.request.Request(upload_url, data=file_bytes, headers=headers, method="POST")
            
            try:
                with urllib.request.urlopen(req) as response:
                    public_url = f"{SUPABASE_URL}/storage/v1/object/public/estimates/{new_filename}"
                    return {"url": public_url}
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8')
                try:
                    error_json = json.loads(error_body)
                    error_msg = error_json.get("message", error_body)
                except:
                    error_msg = error_body
                raise HTTPException(500, detail=f"Supabase 스토리지 에러: {error_msg} (HTTP {e.code})")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(500, detail=f"Supabase 연동 실패: {str(e)}")
    else:
        if IS_VERCEL:
            raise HTTPException(503, detail="Serverless 환경(Vercel)에서는 Supabase 설정이 필수입니다. 로컬 업로드를 지원하지 않습니다.")
        try:
            file_path = os.path.join(UPLOAD_DIR, new_filename)
            with open(file_path, "wb") as buffer:
                buffer.write(file_bytes)
            return {"url": f"/uploads/{new_filename}"}
        except Exception as e:
            raise HTTPException(500, detail=f"로컬 업로드 실패: {str(e)}")

# ── API endpoints ──────────────────────────────────────────────────────────────

# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "ok", "app": "CMhelper v1"}

# ── Auth ───────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=schemas.UserOut, status_code=201)
def api_register(body: schemas.UserCreate, db: Session = Depends(get_db)):
    if body.invite_code != CMHELPER_INVITE_CODE:
        raise HTTPException(status_code=403, detail="Invalid invite code")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    if body.password != body.password_confirm:
        raise HTTPException(status_code=422, detail="Passwords do not match")
    
    email = body.email.strip().lower()
    if crud.get_user_by_email(db, email):
        raise HTTPException(status_code=409, detail="Email already registered")
        
    company = crud.get_or_create_default_company(db, CMHELPER_DEFAULT_COMPANY_NAME, CMHELPER_DEFAULT_COMPANY_SLUG)
    
    role = models.UserRole.OWNER.value if email == CMHELPER_OWNER_EMAIL else models.UserRole.USER.value
    status = models.UserStatus.ACTIVE.value if role == models.UserRole.OWNER.value else models.UserStatus.PENDING.value
    
    # Pass clean email to crud
    body.email = email
    user = crud.create_user(db, body, company.id, role, status)
    return user

@app.post("/api/auth/login", response_model=schemas.Token)
def api_login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = crud.get_user_by_email(db, email)
    if not user or not crud.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.status != models.UserStatus.ACTIVE.value:
        if user.status == models.UserStatus.PENDING.value:
            raise HTTPException(status_code=403, detail="관리자 승인 대기 중인 계정입니다.")
        raise HTTPException(status_code=403, detail="비활성화된 계정입니다.")
        
    if user.company.status != models.CompanyStatus.ACTIVE.value:
        raise HTTPException(status_code=403, detail="Company is inactive")
        
    token_payload = {
        "sub": str(user.id),
        "role": user.role,
        "company_id": user.company_id
    }
    access_token = create_access_token(token_payload)
    return schemas.Token(access_token=access_token)

@app.get("/api/auth/me", response_model=schemas.UserOut)
def api_auth_me(current_user: models.User = Depends(get_current_user)):
    return current_user

# ── Field definitions ──────────────────────────────────────────────────────────

@app.get("/api/fields", response_model=List[schemas.FieldDefOut])
def api_list_fields(active_only: bool = False, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.list_fields(db, active_only)


@app.post("/api/fields", response_model=schemas.FieldDefOut, status_code=201)
def api_create_field(body: schemas.FieldDefCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    row = crud.create_field(db, body)
    if row is None:
        raise HTTPException(400, detail=f"Field name '{body.name}' already exists.")
    return row


@app.put("/api/fields/{fid}", response_model=schemas.FieldDefOut)
def api_update_field(fid: str, body: schemas.FieldDefUpdate,
                     db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    row = crud.update_field(db, fid, body)
    if row is None:
        raise HTTPException(404, detail="Field not found.")
    return row


@app.delete("/api/fields/{fid}")
def api_delete_field(fid: str, db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    if not crud.delete_field(db, fid):
        raise HTTPException(400,
            detail="Cannot delete: field not found or is a system field.")
    return {"deleted": fid}


# ── Customers ──────────────────────────────────────────────────────────────────

def _check_customer_ownership(customer: models.Customer, current_user: models.User):
    if not customer:
        raise HTTPException(404, detail="Customer not found.")
    if customer.company_id != current_user.company_id:
        raise HTTPException(404, detail="Customer not found.")
    if current_user.role == models.UserRole.USER.value and customer.assigned_user_id != current_user.id:
        raise HTTPException(404, detail="Customer not found.")

@app.get("/api/customers", response_model=List[schemas.CustomerOut])
def api_list_customers(search: str = "", skip: int = 0, limit: int = 500,
                       assigned_user_id: Optional[int] = None, scope: Optional[str] = None,
                       db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    
    if current_user.role == models.UserRole.USER.value:
        if scope == "all" or (assigned_user_id is not None and assigned_user_id != current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to view other users' customers")
        effective_user_id = current_user.id
    else:
        # OWNER logic
        if scope == "all":
            effective_user_id = None
        elif assigned_user_id is not None:
            target_user = crud.get_user_by_id(db, assigned_user_id)
            if not target_user or target_user.company_id != current_user.company_id:
                raise HTTPException(status_code=403, detail="Not authorized to view customers of this user")
            effective_user_id = assigned_user_id
        else:
            # Default for OWNER is their own customers
            effective_user_id = current_user.id

    return crud.list_customers(db, company_id=current_user.company_id, assigned_user_id=effective_user_id, search=search, skip=skip, limit=limit)


@app.get("/api/customers/{cid}", response_model=schemas.CustomerOut)
def api_get_customer(cid: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    row = crud.get_customer(db, cid)
    _check_customer_ownership(row, current_user)
    return row


@app.post("/api/customers", response_model=schemas.CustomerOut, status_code=201)
def api_create_customer(body: schemas.CustomerCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.create_customer(db, body, company_id=current_user.company_id, assigned_user_id=current_user.id)


@app.put("/api/customers/{cid}", response_model=schemas.CustomerOut)
def api_update_customer(cid: int, body: schemas.CustomerUpdate,
                        db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    row = crud.get_customer(db, cid)
    _check_customer_ownership(row, current_user)
    updated_row = crud.update_customer(db, cid, body)
    return updated_row


@app.delete("/api/customers/{cid}")
def api_delete_customer(cid: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    row = crud.get_customer(db, cid)
    _check_customer_ownership(row, current_user)
    crud.delete_customer(db, cid)
    return {"deleted": cid}


# ── Consultations ──────────────────────────────────────────────────────────────

@app.post("/api/customers/{cid}/consultations",
          response_model=schemas.ConsultationOut, status_code=201)
def api_add_consultation(cid: int, body: schemas.ConsultationCreate,
                          db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    customer = crud.get_customer(db, cid)
    _check_customer_ownership(customer, current_user)
    row = crud.add_consultation(db, cid, body)
    if not row:
        raise HTTPException(404, detail="Customer not found.")
    return row


@app.delete("/api/consultations/{log_id}")
def api_delete_consultation(log_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    consultation = crud.get_consultation(db, log_id)
    if not consultation:
        raise HTTPException(404, detail="Consultation not found.")
    customer = crud.get_customer(db, consultation.customer_id)
    _check_customer_ownership(customer, current_user)
    crud.delete_consultation(db, log_id)
    return {"deleted": log_id}


# ── Contracts ─────────────────────────────────────────────────────────────────

def _check_contract_ownership(contract: models.Contract, current_user: models.User):
    if not contract:
        raise HTTPException(404, detail="Contract not found.")
    if contract.company_id != current_user.company_id:
        raise HTTPException(403, detail="Forbidden: cross-tenant access.")
    if current_user.role != models.UserRole.OWNER.value:
        if contract.assigned_user_id != current_user.id:
            raise HTTPException(403, detail="Forbidden: not your contract.")


@app.get("/api/contracts", response_model=List[schemas.ContractOut])
def api_list_contracts(
    assigned_user_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    scope: str = "me",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    actual_assigned_user = current_user.id
    if current_user.role == models.UserRole.OWNER.value:
        if scope == "all":
            actual_assigned_user = None
        elif assigned_user_id:
            actual_assigned_user = assigned_user_id
    elif scope == "all" or (assigned_user_id and assigned_user_id != current_user.id):
        raise HTTPException(403, detail="Forbidden: USER cannot view other's contracts")

    # If owner passed a specific user ID, ensure that user belongs to the same company
    if actual_assigned_user and actual_assigned_user != current_user.id:
        target_user = crud.get_user_by_id(db, actual_assigned_user)
        if not target_user or target_user.company_id != current_user.company_id:
            raise HTTPException(403, detail="Forbidden: target user not in company")

    return crud.list_contracts(db, current_user.company_id, customer_id, actual_assigned_user)


@app.get("/api/contracts/{contract_id}", response_model=schemas.ContractOut)
def api_get_contract(contract_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    contract = crud.get_contract(db, contract_id)
    _check_contract_ownership(contract, current_user)
    return contract


@app.post("/api/contracts", response_model=schemas.ContractOut, status_code=201)
def api_create_contract(body: schemas.ContractCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    customer = crud.get_customer(db, body.customer_id)
    _check_customer_ownership(customer, current_user)
    
    if current_user.role == models.UserRole.USER.value:
        if getattr(body, "assigned_user_id", None) is not None and body.assigned_user_id != current_user.id:
            raise HTTPException(403, detail="USER cannot assign contracts to other users.")
        assigned_user_id = current_user.id
    else:
        if getattr(body, "assigned_user_id", None) is not None:
            target_user = crud.get_user_by_id(db, body.assigned_user_id)
            if not target_user or target_user.company_id != current_user.company_id:
                raise HTTPException(403, detail="Forbidden: target user not in company")
            if target_user.status != models.UserStatus.ACTIVE.value:
                raise HTTPException(400, detail="Cannot assign to inactive/pending user.")
            assigned_user_id = body.assigned_user_id
        else:
            assigned_user_id = customer.assigned_user_id
            
    body.expiry_date = crud._compute_expiry(body.contract_date, body.term_months)
    
    return crud.create_contract(db, body, current_user.company_id, assigned_user_id)


@app.patch("/api/contracts/{contract_id}", response_model=schemas.ContractOut)
def api_update_contract(contract_id: int, body: schemas.ContractUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    contract = crud.get_contract(db, contract_id)
    _check_contract_ownership(contract, current_user)
    
    if current_user.role == models.UserRole.USER.value:
        if contract.status in ["COMPLETED", "CANCELLED"]:
            raise HTTPException(403, detail="Historical contracts cannot be modified by USER.")
            
    if body.status is not None and body.status != contract.status:
        if current_user.role == models.UserRole.USER.value:
            if contract.status in ["COMPLETED", "CANCELLED"] or body.status == "ACTIVE":
                raise HTTPException(403, detail="Invalid status transition for USER.")
    
    if body.assigned_user_id is not None and body.assigned_user_id != contract.assigned_user_id:
        if current_user.role != models.UserRole.OWNER.value:
            raise HTTPException(403, detail="Forbidden: Only OWNER can change assigned user.")
        target_user = crud.get_user_by_id(db, body.assigned_user_id)
        if not target_user or target_user.company_id != current_user.company_id:
            raise HTTPException(403, detail="Forbidden: target user not in company")
        if target_user.status != models.UserStatus.ACTIVE.value:
            raise HTTPException(400, detail="Cannot assign to inactive/pending user.")
            
    return crud.update_contract(db, contract_id, body)


@app.delete("/api/contracts/{contract_id}")
def api_delete_contract(contract_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    contract = crud.get_contract(db, contract_id)
    _check_contract_ownership(contract, current_user)
    raise HTTPException(status_code=409, detail="계약 이력은 삭제할 수 없습니다. 계약 상태를 변경해 주세요.")


@app.get("/api/customers/{customer_id}/contracts", response_model=List[schemas.ContractOut])
def api_get_customer_contracts(customer_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    customer = crud.get_customer(db, customer_id)
    _check_customer_ownership(customer, current_user)
    return crud.list_contracts(db, current_user.company_id, customer_id, None)


# ── Opportunity ──────────────────────────────────────────────────────────

def _check_opportunity_ownership(opportunity: models.Opportunity, current_user: models.User):
    if not opportunity:
        raise HTTPException(404, detail="Opportunity not found.")
    if opportunity.company_id != current_user.company_id:
        raise HTTPException(403, detail="Forbidden: cross-tenant access.")
    if current_user.role != models.UserRole.OWNER.value:
        if opportunity.assigned_user_id != current_user.id:
            raise HTTPException(403, detail="Forbidden: not your opportunity.")

@app.get("/api/opportunities", response_model=List[schemas.OpportunityOut])
def api_list_opportunities(
    assigned_user_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    actual_assigned_user = assigned_user_id if current_user.role == models.UserRole.OWNER.value else current_user.id
    return crud.list_opportunities(db, current_user.company_id, customer_id, actual_assigned_user)

@app.get("/api/opportunities/{opportunity_id}", response_model=schemas.OpportunityOut)
def api_get_opportunity(opportunity_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    opp = crud.get_opportunity(db, opportunity_id)
    _check_opportunity_ownership(opp, current_user)
    return opp

@app.post("/api/opportunities", response_model=schemas.OpportunityOut, status_code=201)
def api_create_opportunity(body: schemas.OpportunityCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    customer = crud.get_customer(db, body.customer_id)
    _check_customer_ownership(customer, current_user)
    
    assigned_user_id = body.assigned_user_id
    if current_user.role != models.UserRole.OWNER.value:
        assigned_user_id = current_user.id
    elif assigned_user_id is None:
        assigned_user_id = customer.assigned_user_id
    else:
        target_user = crud.get_user_by_id(db, assigned_user_id)
        if not target_user:
            raise HTTPException(404, detail="User not found.")
        if target_user.company_id != current_user.company_id:
            raise HTTPException(403, detail="Forbidden: cross-tenant assignment.")
        if target_user.status != models.UserStatus.ACTIVE.value:
            raise HTTPException(400, detail="Cannot assign to an inactive user.")
        
    return crud.create_opportunity(db, body, current_user.company_id, assigned_user_id)

@app.patch("/api/opportunities/{opportunity_id}", response_model=schemas.OpportunityOut)
def api_update_opportunity(opportunity_id: int, body: schemas.OpportunityUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    opp = crud.get_opportunity(db, opportunity_id)
    _check_opportunity_ownership(opp, current_user)
    
    if current_user.role != models.UserRole.OWNER.value:
        if body.assigned_user_id is not None and body.assigned_user_id != opp.assigned_user_id:
            raise HTTPException(403, detail="USER cannot reassign opportunities.")
        if opp.status in ["WON", "LOST"]:
            raise HTTPException(403, detail="USER cannot modify closed opportunities.")
    elif body.assigned_user_id is not None:
        target_user = crud.get_user_by_id(db, body.assigned_user_id)
        if not target_user:
            raise HTTPException(404, detail="User not found.")
        if target_user.company_id != current_user.company_id:
            raise HTTPException(403, detail="Forbidden: cross-tenant assignment.")
        if target_user.status != models.UserStatus.ACTIVE.value:
            raise HTTPException(400, detail="Cannot assign to an inactive user.")

    return crud.update_opportunity(db, opportunity_id, body)

@app.get("/api/customers/{customer_id}/opportunities", response_model=List[schemas.OpportunityOut])
def api_get_customer_opportunities(customer_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    customer = crud.get_customer(db, customer_id)
    _check_customer_ownership(customer, current_user)
    
    actual_assigned_user = None if current_user.role == models.UserRole.OWNER.value else current_user.id
    return crud.list_opportunities(db, current_user.company_id, customer_id, actual_assigned_user)

@app.delete("/api/opportunities/{opportunity_id}")
def api_delete_opportunity(opportunity_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    opp = crud.get_opportunity(db, opportunity_id)
    _check_opportunity_ownership(opp, current_user)
    raise HTTPException(status_code=409, detail="Opportunities cannot be hard deleted.")


from sqlalchemy.exc import IntegrityError

@app.post("/api/opportunities/{opportunity_id}/convert-to-contract", response_model=schemas.ContractOut, status_code=201)
def api_convert_opportunity_to_contract(
    opportunity_id: int, 
    data: schemas.OpportunityContractConversionCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    opp = crud.get_opportunity(db, opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Opportunity not found")
        
    _check_opportunity_ownership(opp, current_user)
    
    if opp.status != "WON":
        raise HTTPException(status_code=400, detail="Opportunity is not WON")
        
    # Check application level duplication
    existing = db.query(models.Contract).filter(models.Contract.source_opportunity_id == opportunity_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Opportunity already converted")
        
    if data.source_quote_id:
        quote = crud.get_quote(db, data.source_quote_id)
        if not quote or quote.opportunity_id != opportunity_id or quote.company_id != current_user.company_id:
            raise HTTPException(status_code=404, detail="Quote not found or not related to this Opportunity")
            
    assigned_user_id = current_user.id if current_user.role == models.UserRole.USER.value else (data.assigned_user_id or opp.assigned_user_id)
    
    if current_user.role != models.UserRole.USER.value:
        target_user = crud.get_user_by_id(db, assigned_user_id)
        if not target_user or target_user.company_id != current_user.company_id or target_user.status != models.UserStatus.ACTIVE.value:
            raise HTTPException(status_code=400, detail="Invalid assigned_user_id.")

    row = crud._build_contract_row(data, opp.company_id, opp.customer_id, assigned_user_id)
    row.source_opportunity_id = opportunity_id
    row.source_quote_id = data.source_quote_id
    
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except IntegrityError as e:
        db.rollback()
        err_msg = str(e.orig) if e.orig else str(e)
        if "UNIQUE" in err_msg.upper() and ("source_opportunity_id" in err_msg.lower() or "uq_contracts_source_opportunity" in err_msg.lower()):
            raise HTTPException(status_code=409, detail="Opportunity already converted")
        raise
        
    return row


# ── Quotes ────────────────────────────────────────────────────────────────

def _check_quote_ownership(quote: Optional[models.Quote], current_user: models.User):
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found.")
    if quote.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this quote.")
    if current_user.role == models.UserRole.USER.value and quote.assigned_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this quote.")

@app.post("/api/quotes", response_model=schemas.QuoteOut)
def api_create_quote(data: schemas.QuoteCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    opp = crud.get_opportunity(db, data.opportunity_id)
    _check_opportunity_ownership(opp, current_user)
    
    assigned_user_id = opp.assigned_user_id
    if data.assigned_user_id:
        assigned_user_id = data.assigned_user_id
        
    if current_user.role == models.UserRole.USER.value:
        assigned_user_id = current_user.id
    else:
        target_user = crud.get_user_by_id(db, assigned_user_id)
        if not target_user or target_user.company_id != current_user.company_id or target_user.status != models.UserStatus.ACTIVE.value:
            raise HTTPException(status_code=400, detail="Invalid assigned_user_id.")

    return crud.create_quote(db, data, current_user.company_id, assigned_user_id)

@app.get("/api/quotes", response_model=List[schemas.QuoteOut])
def api_list_quotes(opportunity_id: Optional[int] = None, assigned_user_id: Optional[int] = None, product_type: Optional[str] = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    target_assigned_user_id = assigned_user_id
    if current_user.role == models.UserRole.USER.value:
        target_assigned_user_id = current_user.id
        
    return crud.list_quotes(db, current_user.company_id, opportunity_id, target_assigned_user_id, product_type)

@app.get("/api/opportunities/{opportunity_id}/quotes", response_model=List[schemas.QuoteOut])
def api_list_opportunity_quotes(opportunity_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    opp = crud.get_opportunity(db, opportunity_id)
    _check_opportunity_ownership(opp, current_user)
    
    target_assigned_user_id = None
    if current_user.role == models.UserRole.USER.value:
        target_assigned_user_id = current_user.id
        
    return crud.list_quotes(db, current_user.company_id, opportunity_id, target_assigned_user_id, None)

@app.get("/api/quotes/{quote_id}", response_model=schemas.QuoteOut)
def api_get_quote(quote_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    quote = crud.get_quote(db, quote_id)
    _check_quote_ownership(quote, current_user)
    return quote

@app.patch("/api/quotes/{quote_id}", response_model=schemas.QuoteOut)
def api_update_quote(quote_id: int, data: schemas.QuoteUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    quote = crud.get_quote(db, quote_id)
    _check_quote_ownership(quote, current_user)
    
    if data.assigned_user_id is not None and data.assigned_user_id != quote.assigned_user_id:
        if current_user.role == models.UserRole.USER.value:
            raise HTTPException(status_code=403, detail="USER cannot reassign quotes.")
        target_user = crud.get_user_by_id(db, data.assigned_user_id)
        if not target_user or target_user.company_id != current_user.company_id or target_user.status != models.UserStatus.ACTIVE.value:
            raise HTTPException(status_code=400, detail="Invalid assigned_user_id.")
            
    updated = crud.update_quote(db, quote_id, data)
    return updated

@app.delete("/api/quotes/{quote_id}")
def api_delete_quote(quote_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    quote = crud.get_quote(db, quote_id)
    _check_quote_ownership(quote, current_user)
    raise HTTPException(status_code=409, detail="Quotes cannot be hard deleted.")


# ── Excel import ───────────────────────────────────────────────────────────────

@app.post("/api/excel/parse")
async def api_excel_parse(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    _check_ext(file.filename)
    rows = _read_file(await file.read(), file.filename)
    headers = list(rows[0].keys()) if rows else []
    preview = []
    for r in rows[:5]:
        preview.append({k: str(v) if v is not None else "" for k, v in r.items()})
    return {"headers": headers, "preview": preview}


@app.post("/api/excel/import", response_model=schemas.ImportResult)
async def api_excel_import(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    _check_ext(file.filename)
    try:
        mapping_list: list = json.loads(mapping)
    except Exception:
        raise HTTPException(400, detail="Invalid mapping JSON.")

    rows = _read_file(await file.read(), file.filename)
    columns = list(rows[0].keys()) if rows else []

    system_keys = {
        "name","contact","region","company","contract_car","contract_date","contract_months",
        "capital","product_type","supplies_work","insurance_active","dealer_info",
        "is_prospect","is_contracted","anniversary","memo","estimate_image",
    }

    success = skipped = 0
    errors: List[str] = []

    for i, row in enumerate(rows):
        row_num = i + 2
        try:
            sys_data: dict = {}
            extra_data: dict = {}

            for m in mapping_list:
                ec, db_f = m.get("excel_col", ""), m.get("db_field", "")
                if not ec or not db_f or ec not in columns:
                    continue
                val = row.get(ec)
                if val is None or str(val).strip() == "":
                    val = None
                else:
                    val = str(val).strip()

                if val is not None:
                    if db_f in ("contract_date", "anniversary") and val:
                        import re
                        clean_val = re.sub(r"[^\d]", "", str(val))
                        if len(clean_val) == 8:
                            val = f"{clean_val[:4]}-{clean_val[4:6]}-{clean_val[6:]}"
                    elif db_f in ("contract_months",):
                        try:
                            val = int(float(val))
                        except Exception:
                            val = None
                    elif db_f == "insurance_active":
                        val = val.lower() in ("1", "true", "y", "yes", "예", "가입")
                    elif db_f == "is_prospect":
                        val = val.lower() in ("1", "true", "y", "yes", "예", "가망")
                    elif db_f == "is_contracted":
                        val = val.lower() in ("1", "true", "y", "yes", "예", "기계약")

                if db_f in system_keys:
                    sys_data[db_f] = val
                else:
                    extra_data[db_f] = val

            if not sys_data.get("name"):
                skipped += 1
                errors.append(f"Row {row_num}: '이름' missing — skipped.")
                continue

            crud.create_customer(
                db, 
                schemas.CustomerCreate(
                    name=sys_data.get("name", ""),
                    contact=sys_data.get("contact"),
                    region=sys_data.get("region"),
                    company=sys_data.get("company"),
                    contract_car=sys_data.get("contract_car"),
                    contract_date=sys_data.get("contract_date"),
                    contract_months=sys_data.get("contract_months"),
                    capital=sys_data.get("capital"),
                    product_type=sys_data.get("product_type"),
                    supplies_work=sys_data.get("supplies_work"),
                    insurance_active=sys_data.get("insurance_active", False) or False,
                    dealer_info=sys_data.get("dealer_info"),
                    is_prospect=sys_data.get("is_prospect", False) or False,
                    is_contracted=sys_data.get("is_contracted", False) or False,
                    anniversary=sys_data.get("anniversary"),
                    memo=sys_data.get("memo"),
                    extra=extra_data,
                ),
                company_id=current_user.company_id,
                assigned_user_id=current_user.id
            )
            success += 1
        except Exception as e:
            errors.append(f"Row {row_num}: {e}")

    return schemas.ImportResult(success=success, skipped=skipped, errors=errors)


# ── helpers ────────────────────────────────────────────────────────────────────

def _check_ext(filename: str):
    if not filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400,
            detail="Only .xlsx / .xls / .csv files are accepted.")

def _read_file(content: bytes, filename: str) -> List[dict]:
    try:
        if filename.lower().endswith(".csv"):
            text = content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            rows = []
            if reader.fieldnames:
                headers = [str(h).strip() for h in reader.fieldnames]
                reader.fieldnames = headers
                for row in reader:
                    rows.append(row)
            return rows

        wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
        sheet = wb.active
        
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            headers_raw = next(rows_iter)
        except StopIteration:
            return []
            
        headers = [str(h).strip() if h is not None else f"Column_{i}" for i, h in enumerate(headers_raw)]
        
        data = []
        for row in rows_iter:
            row_dict = {}
            for i, h in enumerate(headers):
                val = row[i] if i < len(row) else None
                row_dict[h] = val
            data.append(row_dict)
        return data
    except Exception as e:
        raise HTTPException(400, detail=f"Could not parse file: {e}")

# ── MessageTask Endpoints ─────────────────────────────────────────────────────

@app.post("/api/messages/queue", response_model=List[schemas.MessageTaskOut])
def api_queue_messages(tasks: List[schemas.MessageTaskCreate], db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    results = []
    try:
        for t in tasks:
            customer = crud.get_customer(db, t.customer_id)
            _check_customer_ownership(customer, current_user)
            row = crud.create_message_task(db, t)
            results.append(row)
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"발송 대기열 저장 실패: {str(e)}")

@app.get("/api/messages/pending", response_model=List[schemas.MessageTaskOut])
def api_get_pending_messages(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    assigned_user_id = current_user.id if current_user.role == models.UserRole.USER.value else None
    return crud.get_pending_message_tasks(db, company_id=current_user.company_id, assigned_user_id=assigned_user_id)

@app.get("/api/messages/history", response_model=List[schemas.MessageTaskOut])
def api_get_message_history(limit: int = 200, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    assigned_user_id = current_user.id if current_user.role == models.UserRole.USER.value else None
    return crud.get_recent_message_tasks(db, company_id=current_user.company_id, assigned_user_id=assigned_user_id, limit=limit)

@app.delete("/api/messages/pending")
def api_cancel_pending_messages(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    assigned_user_id = current_user.id if current_user.role == models.UserRole.USER.value else None
    count = crud.cancel_pending_message_tasks(db, company_id=current_user.company_id, assigned_user_id=assigned_user_id)
    return {"detail": f"Canceled {count} tasks."}

@app.put("/api/messages/{task_id}/status", response_model=schemas.MessageTaskOut)
def api_update_message_status(task_id: int, body: schemas.MessageTaskUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    task = crud.get_message_task(db, task_id)
    if not task:
        raise HTTPException(404, detail="Message task not found")
    customer = crud.get_customer(db, task.customer_id)
    _check_customer_ownership(customer, current_user)

    row = crud.update_message_task_status(db, task_id, body.status)
    if not row:
        raise HTTPException(404, detail="Message task not found")
    
    if body.status == "sent" and row.image_url and supabase:
        try:
            filename = row.image_url.split("/")[-1]
            supabase.storage.from_("estimates").remove([filename])
        except Exception as e:
            print(f"Failed to delete image {filename}: {e}")
            
    return row

# ── User Management Endpoints ──────────────────────────────────────────────────

@app.get("/api/admin/users", response_model=List[schemas.UserOut])
def api_admin_list_users(db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    return crud.get_users_by_company(db, current_user.company_id)

@app.patch("/api/admin/users/{user_id}/status", response_model=schemas.UserOut)
def api_admin_update_user_status(user_id: int, body: schemas.UserStatusUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    if user_id == current_user.id:
        raise HTTPException(status_code=403, detail="자신의 상태는 변경할 수 없습니다.")
        
    target_user = crud.get_user_by_id(db, user_id)
    if not target_user or target_user.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="User not found")
        
    if body.status not in [models.UserStatus.ACTIVE.value, models.UserStatus.INACTIVE.value, models.UserStatus.PENDING.value]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    updated = crud.update_user_status(db, user_id, body.status)
    return updated

