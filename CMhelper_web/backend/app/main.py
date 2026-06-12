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
    """Forward-only column migrations for SQLite (safe to run every startup)."""
    with eng.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(customers)"))
        existing = {row[1] for row in result.fetchall()}

        new_cols = [
            ("contact",         "VARCHAR"),
            ("region",          "VARCHAR"),
            ("contract_date",   "VARCHAR"),
            ("contract_months", "INTEGER"),
            ("expiry_date",     "VARCHAR"),
            ("capital",         "VARCHAR"),
            ("product_type",    "VARCHAR"),
            ("is_prospect",     "BOOLEAN DEFAULT 0"),
            ("is_contracted",   "BOOLEAN DEFAULT 0"),
            ("anniversary",     "VARCHAR"),
            ("memo",            "VARCHAR"),
            ("estimate_image",  "VARCHAR"),
            ("extra",           "TEXT DEFAULT '{}'"),
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing:
                conn.execute(text(
                    f"ALTER TABLE customers ADD COLUMN {col_name} {col_type}"
                ))
        conn.commit()


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

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    new_filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"url": f"/uploads/{new_filename}"}

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
