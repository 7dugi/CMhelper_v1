"""All database read/write operations."""
from __future__ import annotations

import calendar
import datetime
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from . import models, schemas


# ── Expiry computation helper ──────────────────────────────────────────────────

def _compute_expiry(contract_date_str: Optional[str],
                    contract_months: Optional[int]) -> Optional[str]:
    """Return YYYY-MM-DD expiry date, or None if inputs are missing/invalid."""
    if not contract_date_str or not contract_months:
        return None
    try:
        parts = contract_date_str.split('-')
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        months = int(contract_months)
        month += months
        while month > 12:
            month -= 12
            year += 1
        # Clamp to last day of target month
        max_day = calendar.monthrange(year, month)[1]
        day = min(day, max_day)
        return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception:
        return None


# ── System field definitions ───────────────────────────────────────────────────

_SYSTEM_FIELDS = [
    dict(name="name",             label="이름",              field_type="text",     sort_order=1),
    dict(name="company",          label="업체명",             field_type="text",     sort_order=2),
    dict(name="contract_car",     label="계약차종",            field_type="text",     sort_order=3),
    dict(name="contract_date",    label="계약일(인도일)",       field_type="date",     sort_order=4),
    dict(name="contract_months",  label="계약 개월수",         field_type="select",   sort_order=5,
         options=["24", "36", "48", "60"]),
    dict(name="expiry_date",      label="만기일",              field_type="date",     sort_order=6),
    dict(name="capital",          label="캐피탈",             field_type="text",     sort_order=7),
    dict(name="supplies_work",    label="용품작업내용+업체명",  field_type="text",     sort_order=8),
    dict(name="insurance_active", label="보험가입여부",         field_type="boolean",  sort_order=9),
    dict(name="dealer_info",      label="담당 딜러+딜러사",     field_type="text",     sort_order=10),
    dict(name="is_prospect",      label="가망고객",            field_type="boolean",  sort_order=11),
    dict(name="is_contracted",    label="기계약 고객",          field_type="boolean",  sort_order=12),
    dict(name="anniversary",      label="기념일",              field_type="date",     sort_order=13),
    dict(name="memo",             label="기타 메모사항",       field_type="textarea", sort_order=14),
]

_SYSTEM_NAMES      = {f["name"] for f in _SYSTEM_FIELDS}
_DEPRECATED_NAMES  = {"months"}   # removed from system – clean up if found


def seed_defaults(db: Session) -> None:
    """Idempotent: remove deprecated system fields, add/update current ones."""
    # Remove deprecated system fields
    for dep in _DEPRECATED_NAMES:
        old = db.query(models.FieldDefinition).filter_by(name=dep, is_system=True).first()
        if old:
            db.delete(old)

    # Add missing system fields / ensure flags are correct
    for f in _SYSTEM_FIELDS:
        existing = db.query(models.FieldDefinition).filter_by(name=f["name"]).first()
        if not existing:
            db.add(models.FieldDefinition(
                id=str(uuid.uuid4()),
                is_system=True,
                is_active=True,
                **f,
            ))
        else:
            existing.is_system = True
            if "options" in f:
                existing.options = f["options"]

    db.commit()


# ── Field definitions ──────────────────────────────────────────────────────────

def list_fields(db: Session, active_only: bool = False) -> List[models.FieldDefinition]:
    q = db.query(models.FieldDefinition)
    if active_only:
        q = q.filter(models.FieldDefinition.is_active.is_(True))
    return q.order_by(models.FieldDefinition.sort_order).all()


def create_field(db: Session, data: schemas.FieldDefCreate) -> Optional[models.FieldDefinition]:
    if db.query(models.FieldDefinition).filter_by(name=data.name).first():
        return None
    row = models.FieldDefinition(
        id=str(uuid.uuid4()),
        name=data.name,
        label=data.label,
        field_type=data.field_type,
        options=data.options,
        is_system=False,
        is_active=True,
        sort_order=data.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_field(db: Session, fid: str,
                 data: schemas.FieldDefUpdate) -> Optional[models.FieldDefinition]:
    row = db.query(models.FieldDefinition).filter_by(id=fid).first()
    if not row:
        return None
    patch = data.model_dump(exclude_unset=True)
    # System fields: only label / is_active / sort_order may be changed
    if row.is_system:
        patch = {k: v for k, v in patch.items()
                 if k in ("label", "is_active", "sort_order")}
    for k, v in patch.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def delete_field(db: Session, fid: str) -> bool:
    row = db.query(models.FieldDefinition).filter_by(id=fid).first()
    if not row or row.is_system:
        return False
    # Scrub this key from every customer's extra dict
    for c in db.query(models.Customer).all():
        if c.extra and row.name in c.extra:
            new_extra = dict(c.extra)
            new_extra.pop(row.name)
            c.extra = new_extra
    db.delete(row)
    db.commit()
    return True


# ── Customers ──────────────────────────────────────────────────────────────────

def list_customers(db: Session, search: str = "",
                   skip: int = 0, limit: int = 500) -> List[models.Customer]:
    q = db.query(models.Customer)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            models.Customer.name.ilike(like),
            models.Customer.company.ilike(like),
            models.Customer.contract_car.ilike(like),
            models.Customer.capital.ilike(like),
            models.Customer.dealer_info.ilike(like),
            models.Customer.memo.ilike(like),
        ))
    return q.order_by(models.Customer.id.desc()).offset(skip).limit(limit).all()


def get_customer(db: Session, cid: int) -> Optional[models.Customer]:
    return db.query(models.Customer).filter_by(id=cid).first()


def create_customer(db: Session, data: schemas.CustomerCreate) -> models.Customer:
    expiry = _compute_expiry(data.contract_date, data.contract_months)
    row = models.Customer(
        name=data.name,
        company=data.company,
        contract_car=data.contract_car,
        contract_date=data.contract_date,
        contract_months=data.contract_months,
        expiry_date=expiry,
        capital=data.capital,
        supplies_work=data.supplies_work,
        insurance_active=data.insurance_active,
        dealer_info=data.dealer_info,
        is_prospect=data.is_prospect,
        is_contracted=data.is_contracted,
        anniversary=data.anniversary,
        memo=data.memo,
        extra=data.extra or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_customer(db: Session, cid: int,
                    data: schemas.CustomerUpdate) -> Optional[models.Customer]:
    row = get_customer(db, cid)
    if not row:
        return None
    patch = data.model_dump(exclude_unset=True)
    if "extra" in patch and patch["extra"] is not None:
        merged = dict(row.extra or {})
        merged.update(patch.pop("extra"))
        row.extra = merged
    for k, v in patch.items():
        setattr(row, k, v)
    # Recompute expiry whenever contract fields change
    if "contract_date" in patch or "contract_months" in patch:
        row.expiry_date = _compute_expiry(row.contract_date, row.contract_months)
    row.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def delete_customer(db: Session, cid: int) -> bool:
    row = get_customer(db, cid)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


# ── Consultations ──────────────────────────────────────────────────────────────

def add_consultation(db: Session, cid: int,
                     data: schemas.ConsultationCreate) -> Optional[models.Consultation]:
    if not get_customer(db, cid):
        return None
    row = models.Consultation(customer_id=cid, notes=data.notes)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_consultation(db: Session, log_id: int) -> bool:
    row = db.query(models.Consultation).filter_by(id=log_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
