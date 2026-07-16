"""All database read/write operations."""
from __future__ import annotations

import calendar
import datetime
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

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
    dict(name="name",             label="이름",              field_type="text",     sort_order=1, target_type="common"),
    dict(name="contact",          label="연락처",             field_type="text",     sort_order=2, target_type="common"),
    dict(name="region",           label="지역",               field_type="text",     sort_order=3, target_type="common"),
    dict(name="company",          label="업체명",             field_type="text",     sort_order=4, target_type="common"),
    dict(name="contract_car",     label="계약차종",            field_type="text",     sort_order=5, target_type="common"),
    dict(name="contract_date",    label="계약일(인도일)",       field_type="date",     sort_order=6, target_type="contracted"),
    dict(name="contract_months",  label="계약 개월수",         field_type="select",   sort_order=7,
         options=["24", "36", "48", "60"], target_type="contracted"),
    dict(name="expiry_date",      label="만기일",              field_type="date",     sort_order=8, target_type="contracted"),
    dict(name="capital",          label="캐피탈",             field_type="text",     sort_order=9, target_type="contracted"),
    dict(name="product_type",     label="상품",               field_type="select",   sort_order=10,
         options=["장기렌트", "리스", "할부", "일시불"], target_type="contracted"),
    dict(name="supplies_work",    label="용품작업내용+업체명",  field_type="text",     sort_order=11, target_type="contracted"),
    dict(name="insurance_active", label="보험가입여부",         field_type="boolean",  sort_order=12, target_type="contracted"),
    dict(name="dealer_info",      label="담당 딜러+딜러사",     field_type="text",     sort_order=13, target_type="contracted"),
    dict(name="is_prospect",      label="가망고객",            field_type="boolean",  sort_order=14, target_type="prospect"),
    dict(name="is_contracted",    label="기계약 고객",          field_type="boolean",  sort_order=15, target_type="contracted"),
    dict(name="anniversary",      label="기념일",              field_type="date",     sort_order=16, target_type="contracted"),
    dict(name="memo",             label="기타 메모사항",       field_type="textarea", sort_order=17, target_type="common"),
    dict(name="estimate_image",   label="견적서 첨부",         field_type="image",    sort_order=18, target_type="contracted"),
    dict(name="sent_quotes",      label="보낸 견적함",         field_type="image_gallery", sort_order=19, target_type="prospect"),
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
                name=f["name"], label=f["label"], field_type=f["field_type"],
                sort_order=f["sort_order"], options=f.get("options"),
                is_system=True, is_active=True, target_type=f.get("target_type", "contracted")
            ))
        else:
            existing.is_system = True
            existing.target_type = f.get("target_type", "contracted")
            if "options" in f:
                existing.options = f["options"]

    try:
        db.commit()
    except IntegrityError:
        db.rollback()


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
        target_type=data.target_type,
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
        contact=data.contact,
        region=data.region,
        company=data.company,
        contract_car=data.contract_car,
        contract_date=data.contract_date,
        contract_months=data.contract_months,
        expiry_date=expiry,
        capital=data.capital,
        product_type=data.product_type,
        supplies_work=data.supplies_work,
        insurance_active=data.insurance_active,
        dealer_info=data.dealer_info,
        is_prospect=data.is_prospect,
        is_contracted=data.is_contracted,
        anniversary=data.anniversary,
        memo=data.memo,
        estimate_image=data.estimate_image,
        sent_quotes=data.sent_quotes or [],
        extra=data.extra or {},
    )
    db.add(row)
    db.flush() # get row.id without committing
    
    if data.initial_consultation:
        consultation = models.Consultation(customer_id=row.id, notes=data.initial_consultation)
        db.add(consultation)

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

# ── Message Tasks ─────────────────────────────────────────────────────────────

def create_message_task(db: Session, data: schemas.MessageTaskCreate) -> models.MessageTask:
    row = models.MessageTask(**data.model_dump())
    if row.status == "pending":
        row.status = "RESERVED"  # Upgrading old default just in case
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def _format_message_tasks(tasks: List[models.MessageTask]) -> List[schemas.MessageTaskOut]:
    results = []
    for t in tasks:
        out = schemas.MessageTaskOut.model_validate(t)
        if t.customer:
            out.customer_name = t.customer.name
            out.customer_contact = t.customer.contact
        results.append(out)
    return results

def recover_orphan_tasks(db: Session):
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(minutes=5)
    orphans = db.query(models.MessageTask).filter(
        models.MessageTask.status == "PROCESSING",
        models.MessageTask.heartbeat_at < cutoff
    ).all()
    for o in orphans:
        o.retry_count += 1
        if o.retry_count < 2:
            o.status = "RECOVERY"
            o.error_code = "HEARTBEAT_TIMEOUT"
        else:
            o.status = "FAILED"
            o.error_code = "MAX_RETRY_EXCEEDED"
    if orphans:
        db.commit()

def get_pending_message_tasks(db: Session, agent_uuid: str) -> List[schemas.MessageTaskOut]:
    recover_orphan_tasks(db)
    
    now = datetime.datetime.utcnow()
    # Find candidates
    tasks_to_process = db.query(models.MessageTask.id).filter(
        models.MessageTask.status.in_(["RESERVED", "RECOVERY"]),
        or_(
            models.MessageTask.scheduled_at == None,
            models.MessageTask.scheduled_at <= now
        )
    ).order_by(models.MessageTask.created_at.asc()).limit(50).all()
    
    if not tasks_to_process:
        return []
        
    ids = [t[0] for t in tasks_to_process]
    
    # Atomic Lock
    db.query(models.MessageTask).filter(
        models.MessageTask.id.in_(ids)
    ).update({
        models.MessageTask.status: "PROCESSING",
        models.MessageTask.locked_by: agent_uuid,
        models.MessageTask.locked_at: now,
        models.MessageTask.heartbeat_at: now
    }, synchronize_session=False)
    db.commit()
    
    # Return locked tasks
    locked_tasks = db.query(models.MessageTask).filter(
        models.MessageTask.id.in_(ids),
        models.MessageTask.locked_by == agent_uuid
    ).order_by(models.MessageTask.created_at.asc()).all()
    
    return _format_message_tasks(locked_tasks)

def cancel_pending_message_tasks(db: Session) -> int:
    tasks = db.query(models.MessageTask).filter(models.MessageTask.status.in_(["RESERVED", "RECOVERY"])).all()
    count = 0
    for t in tasks:
        t.status = "CANCELLED"
        t.error_code = "Canceled by user"
        count += 1
    db.commit()
    return count

def get_recent_message_tasks(db: Session, limit: int = 200) -> List[schemas.MessageTaskOut]:
    tasks = db.query(models.MessageTask).order_by(models.MessageTask.created_at.desc()).limit(limit).all()
    return _format_message_tasks(tasks)

def update_message_task_status(db: Session, task_id: int, data: schemas.MessageTaskUpdate) -> Optional[models.MessageTask]:
    row = db.query(models.MessageTask).filter_by(id=task_id).first()
    if not row:
        return None
    
    patch = data.model_dump(exclude_unset=True)
    if "status" in patch:
        if patch["status"] in ["RECOVERY", "FAILED"] and row.status == "PROCESSING":
            row.retry_count += 1
            if row.retry_count >= 2:
                row.status = "FAILED"
                row.error_code = "MAX_RETRY_EXCEEDED"
            else:
                row.status = patch["status"]
                if "error_code" in patch:
                    row.error_code = patch["error_code"]
        else:
            row.status = patch["status"]
            if "error_code" in patch:
                row.error_code = patch["error_code"]
    
    if "heartbeat_at" in patch:
        row.heartbeat_at = patch["heartbeat_at"]
        
    db.commit()
    db.refresh(row)
    return row

def update_task_heartbeat(db: Session, task_id: int, agent_uuid: str) -> bool:
    row = db.query(models.MessageTask).filter_by(id=task_id, locked_by=agent_uuid, status="PROCESSING").first()
    if not row:
        return False
    row.heartbeat_at = datetime.datetime.utcnow()
    db.commit()
    return True
