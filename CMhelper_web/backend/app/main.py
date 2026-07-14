"""CMhelper v1 — FastAPI backend entry point"""
from __future__ import annotations

import io
import json
from typing import List

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from . import crud, models, schemas


# ── DB bootstrap ───────────────────────────────────────────────────────────────

Base.metadata.create_all(bind=engine)


def run_migrations(eng) -> None:
    """Forward-only column migrations for SQLite and Postgres."""
    dialect = eng.dialect.name
    with eng.begin() as conn:
        if dialect == "sqlite":
            result = conn.execute(text("PRAGMA table_info(customers)"))
            existing_cust = {row[1] for row in result.fetchall()}
            result = conn.execute(text("PRAGMA table_info(field_definitions)"))
            existing_fd = {row[1] for row in result.fetchall()}
        else:
            # PostgreSQL
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='customers'"))
            existing_cust = {row[0] for row in result.fetchall()}
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='field_definitions'"))
            existing_fd = {row[0] for row in result.fetchall()}

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


run_migrations(engine)

# Seed default field definitions once
_boot_db = next(get_db())
try:
    crud.seed_defaults(_boot_db)
finally:
    _boot_db.close()


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="CMhelper v1", version="1.0.0")

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
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    new_filename = f"{uuid.uuid4().hex}.{ext}"
    file_bytes = await file.read()

    if supabase:
        try:
            res = supabase.storage.from_("estimates").upload(
                path=new_filename,
                file=file_bytes,
                file_options={"content-type": file.content_type}
            )
            public_url = supabase.storage.from_("estimates").get_public_url(new_filename)
            return {"url": public_url}
        except Exception as e:
            raise HTTPException(500, detail=f"Supabase 업로드 실패: {str(e)}")
    else:
        try:
            file_path = os.path.join(UPLOAD_DIR, new_filename)
            with open(file_path, "wb") as buffer:
                buffer.write(file_bytes)
            return {"url": f"/uploads/{new_filename}"}
        except Exception as e:
            raise HTTPException(500, detail=f"로컬 업로드 실패 (서버 환경에서는 Supabase 연동이 필수입니다): {str(e)}")

# ── API endpoints ──────────────────────────────────────────────────────────────

# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "ok", "app": "CMhelper v1"}


# ── Field definitions ──────────────────────────────────────────────────────────

@app.get("/api/fields", response_model=List[schemas.FieldDefOut])
def api_list_fields(active_only: bool = False, db: Session = Depends(get_db)):
    return crud.list_fields(db, active_only)


@app.post("/api/fields", response_model=schemas.FieldDefOut, status_code=201)
def api_create_field(body: schemas.FieldDefCreate, db: Session = Depends(get_db)):
    row = crud.create_field(db, body)
    if row is None:
        raise HTTPException(400, detail=f"Field name '{body.name}' already exists.")
    return row


@app.put("/api/fields/{fid}", response_model=schemas.FieldDefOut)
def api_update_field(fid: str, body: schemas.FieldDefUpdate,
                     db: Session = Depends(get_db)):
    row = crud.update_field(db, fid, body)
    if row is None:
        raise HTTPException(404, detail="Field not found.")
    return row


@app.delete("/api/fields/{fid}")
def api_delete_field(fid: str, db: Session = Depends(get_db)):
    if not crud.delete_field(db, fid):
        raise HTTPException(400,
            detail="Cannot delete: field not found or is a system field.")
    return {"deleted": fid}


# ── Customers ──────────────────────────────────────────────────────────────────

@app.get("/api/customers", response_model=List[schemas.CustomerOut])
def api_list_customers(search: str = "", skip: int = 0, limit: int = 500,
                       db: Session = Depends(get_db)):
    return crud.list_customers(db, search=search, skip=skip, limit=limit)


@app.get("/api/customers/{cid}", response_model=schemas.CustomerOut)
def api_get_customer(cid: int, db: Session = Depends(get_db)):
    row = crud.get_customer(db, cid)
    if not row:
        raise HTTPException(404, detail="Customer not found.")
    return row


@app.post("/api/customers", response_model=schemas.CustomerOut, status_code=201)
def api_create_customer(body: schemas.CustomerCreate, db: Session = Depends(get_db)):
    return crud.create_customer(db, body)


@app.put("/api/customers/{cid}", response_model=schemas.CustomerOut)
def api_update_customer(cid: int, body: schemas.CustomerUpdate,
                        db: Session = Depends(get_db)):
    row = crud.update_customer(db, cid, body)
    if not row:
        raise HTTPException(404, detail="Customer not found.")
    return row


@app.delete("/api/customers/{cid}")
def api_delete_customer(cid: int, db: Session = Depends(get_db)):
    if not crud.delete_customer(db, cid):
        raise HTTPException(404, detail="Customer not found.")
    return {"deleted": cid}


# ── Consultations ──────────────────────────────────────────────────────────────

@app.post("/api/customers/{cid}/consultations",
          response_model=schemas.ConsultationOut, status_code=201)
def api_add_consultation(cid: int, body: schemas.ConsultationCreate,
                          db: Session = Depends(get_db)):
    row = crud.add_consultation(db, cid, body)
    if not row:
        raise HTTPException(404, detail="Customer not found.")
    return row


@app.delete("/api/consultations/{log_id}")
def api_delete_consultation(log_id: int, db: Session = Depends(get_db)):
    if not crud.delete_consultation(db, log_id):
        raise HTTPException(404, detail="Consultation not found.")
    return {"deleted": log_id}


# ── Excel import ───────────────────────────────────────────────────────────────

@app.post("/api/excel/parse")
async def api_excel_parse(file: UploadFile = File(...)):
    _check_ext(file.filename)
    df = _read_file(await file.read(), file.filename)
    headers = [str(c).strip() for c in df.columns]
    preview = df.head(5).fillna("").astype(str).to_dict(orient="records")
    return {"headers": headers, "preview": preview}


@app.post("/api/excel/import", response_model=schemas.ImportResult)
async def api_excel_import(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    db: Session = Depends(get_db),
):
    _check_ext(file.filename)
    try:
        mapping_list: list = json.loads(mapping)
    except Exception:
        raise HTTPException(400, detail="Invalid mapping JSON.")

    df = _read_file(await file.read(), file.filename)
    df.columns = [str(c).strip() for c in df.columns]

    system_keys = {
        "name","contact","region","company","contract_car","contract_date","contract_months",
        "capital","product_type","supplies_work","insurance_active","dealer_info",
        "is_prospect","is_contracted","anniversary","memo","estimate_image",
    }

    success = skipped = 0
    errors: List[str] = []

    for i, row in df.iterrows():
        row_num = i + 2
        try:
            sys_data: dict = {}
            extra_data: dict = {}

            for m in mapping_list:
                ec, db_f = m.get("excel_col", ""), m.get("db_field", "")
                if not ec or not db_f or ec not in df.columns:
                    continue
                val = row[ec]
                if pd.isna(val) or str(val).strip() == "":
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

            crud.create_customer(db, schemas.CustomerCreate(
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
            ))
            success += 1
        except Exception as e:
            errors.append(f"Row {row_num}: {e}")

    return schemas.ImportResult(success=success, skipped=skipped, errors=errors)


# ── helpers ────────────────────────────────────────────────────────────────────

def _check_ext(filename: str):
    if not filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400,
            detail="Only .xlsx / .xls / .csv files are accepted.")

def _read_file(content: bytes, filename: str) -> pd.DataFrame:
    try:
        if filename.lower().endswith(".csv"):
            return pd.read_csv(io.BytesIO(content))
        return pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, detail=f"Could not parse file: {e}")

# ── MessageTask Endpoints ─────────────────────────────────────────────────────

@app.post("/api/messages/queue", response_model=List[schemas.MessageTaskOut])
def api_queue_messages(tasks: List[schemas.MessageTaskCreate], db: Session = Depends(get_db)):
    results = []
    try:
        for t in tasks:
            row = crud.create_message_task(db, t)
            results.append(row)
        return results
    except Exception as e:
        raise HTTPException(500, detail=f"발송 대기열 저장 실패: {str(e)}")

@app.get("/api/messages/pending", response_model=List[schemas.MessageTaskOut])
def api_get_pending_messages(db: Session = Depends(get_db)):
    return crud.get_pending_message_tasks(db)

@app.get("/api/messages/history", response_model=List[schemas.MessageTaskOut])
def api_get_message_history(limit: int = 200, db: Session = Depends(get_db)):
    return crud.get_recent_message_tasks(db, limit=limit)

@app.delete("/api/messages/pending")
def api_cancel_pending_messages(db: Session = Depends(get_db)):
    count = crud.cancel_pending_message_tasks(db)
    return {"detail": f"Canceled {count} tasks."}

@app.put("/api/messages/{task_id}/status", response_model=schemas.MessageTaskOut)
def api_update_message_status(task_id: int, body: schemas.MessageTaskUpdate, db: Session = Depends(get_db)):
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
