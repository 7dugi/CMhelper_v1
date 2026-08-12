"""All database read/write operations."""
from __future__ import annotations

import calendar
import datetime
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

import bcrypt
from . import models, schemas

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_byte_enc = plain_password.encode('utf-8')
        hashed_password_byte_enc = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)
    except Exception:
        return False

# ── Auth & Users ──────────────────────────────────────────────────────────────

def get_or_create_default_company(db: Session, name: str, slug: str) -> models.Company:
    company = db.query(models.Company).filter_by(slug=slug).first()
    if company:
        return company
    try:
        new_company = models.Company(name=name, slug=slug)
        db.add(new_company)
        db.commit()
        db.refresh(new_company)
        return new_company
    except IntegrityError:
        db.rollback()
        # Concurrent creation handle
        return db.query(models.Company).filter_by(slug=slug).first()

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter_by(email=email).first()

def create_user(db: Session, data: schemas.UserCreate, company_id: int, role: str, status: str) -> models.User:
    hashed_password = get_password_hash(data.password)
    user = models.User(
        company_id=company_id,
        email=data.email,
        password_hash=hashed_password,
        name=data.name,
        role=role,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_users_by_company(db: Session, company_id: int) -> List[models.User]:
    return db.query(models.User).filter(models.User.company_id == company_id).order_by(models.User.created_at.desc()).all()

def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()

def update_user_status(db: Session, user_id: int, status: str) -> Optional[models.User]:
    user = get_user_by_id(db, user_id)
    if user:
        user.status = status
        db.commit()
        db.refresh(user)
    return user



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

def list_customers(db: Session, company_id: int, assigned_user_id: Optional[int] = None,
                   search: str = "", skip: int = 0, limit: int = 500) -> List[models.Customer]:
    from sqlalchemy import func, case
    today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    contracts_sq = db.query(
        models.Contract.customer_id,
        func.count(models.Contract.id).label("contract_count"),
        func.min(
            case(
                (models.Contract.expiry_date >= today_str, models.Contract.expiry_date),
                else_=None
            )
        ).label("nearest_expiry")
    ).group_by(models.Contract.customer_id).subquery()

    q = db.query(models.Customer, contracts_sq.c.contract_count, contracts_sq.c.nearest_expiry)\
          .outerjoin(contracts_sq, models.Customer.id == contracts_sq.c.customer_id)\
          .options(joinedload(models.Customer.assigned_user))\
          .filter(models.Customer.company_id == company_id)

    if assigned_user_id is not None:
        q = q.filter(models.Customer.assigned_user_id == assigned_user_id)
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
        
    results = q.order_by(models.Customer.id.desc()).offset(skip).limit(limit).all()
    customers = []
    for c, cnt, exp in results:
        c.contract_count = cnt or 0
        c.nearest_expiry = exp
        customers.append(c)
    return customers


def get_customer(db: Session, cid: int) -> Optional[models.Customer]:
    from sqlalchemy import func, case
    today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    contracts_sq = db.query(
        models.Contract.customer_id,
        func.count(models.Contract.id).label("contract_count"),
        func.min(
            case(
                (models.Contract.expiry_date >= today_str, models.Contract.expiry_date),
                else_=None
            )
        ).label("nearest_expiry")
    ).group_by(models.Contract.customer_id).subquery()

    row = db.query(models.Customer, contracts_sq.c.contract_count, contracts_sq.c.nearest_expiry)\
            .outerjoin(contracts_sq, models.Customer.id == contracts_sq.c.customer_id)\
            .options(joinedload(models.Customer.assigned_user))\
            .filter(models.Customer.id == cid).first()
            
    if row:
        c, cnt, exp = row
        c.contract_count = cnt or 0
        c.nearest_expiry = exp
        return c
    return None


def create_customer(db: Session, data: schemas.CustomerCreate, company_id: int, assigned_user_id: int) -> models.Customer:
    expiry = _compute_expiry(data.contract_date, data.contract_months)
    row = models.Customer(
        company_id=company_id,
        assigned_user_id=assigned_user_id,
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
    
    # 2D.2 Dual-write (Transactional): Create Contract row if any contract info is provided
    has_contract = any([
        data.contract_car, data.contract_date, data.contract_months, 
        data.expiry_date, data.capital, data.product_type
    ])
    
    if has_contract:
        from app.models import Contract
        contract = Contract(
            company_id=company_id,
            customer_id=row.id,
            assigned_user_id=assigned_user_id,
            legacy_origin_customer_id=None,  # 2D.2 Rule: NULL for new contracts
            vehicle_model=data.contract_car,
            contract_date=data.contract_date,
            term_months=data.contract_months,
            expiry_date=expiry,
            capital=data.capital,
            product_type=data.product_type,
            supplies_work=data.supplies_work,
            insurance_active=data.insurance_active,
            dealer_info=data.dealer_info,
            status="ACTIVE"
        )
        db.add(contract)

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


def get_consultation(db: Session, log_id: int) -> Optional[models.Consultation]:
    return db.query(models.Consultation).filter_by(id=log_id).first()

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

def get_pending_message_tasks(db: Session, company_id: int, assigned_user_id: Optional[int] = None) -> List[schemas.MessageTaskOut]:
    now = datetime.datetime.utcnow()
    q = db.query(models.MessageTask).join(models.Customer).filter(
        models.Customer.company_id == company_id,
        models.MessageTask.status == "pending",
        or_(
            models.MessageTask.scheduled_at == None,
            models.MessageTask.scheduled_at <= now
        )
    )
    if assigned_user_id is not None:
        q = q.filter(models.Customer.assigned_user_id == assigned_user_id)
    tasks = q.order_by(models.MessageTask.created_at.asc()).all()
    return _format_message_tasks(tasks)

def cancel_pending_message_tasks(db: Session, company_id: int, assigned_user_id: Optional[int] = None) -> int:
    q = db.query(models.MessageTask).join(models.Customer).filter(
        models.Customer.company_id == company_id,
        models.MessageTask.status == "pending"
    )
    if assigned_user_id is not None:
        q = q.filter(models.Customer.assigned_user_id == assigned_user_id)
    tasks = q.all()
    count = 0
    for t in tasks:
        t.status = "failed"
        t.error_message = "Canceled by user"
        count += 1
    db.commit()
    return count

def get_recent_message_tasks(db: Session, company_id: int, assigned_user_id: Optional[int] = None, limit: int = 200) -> List[schemas.MessageTaskOut]:
    q = db.query(models.MessageTask).join(models.Customer).filter(
        models.Customer.company_id == company_id
    )
    if assigned_user_id is not None:
        q = q.filter(models.Customer.assigned_user_id == assigned_user_id)
    tasks = q.order_by(models.MessageTask.created_at.desc()).limit(limit).all()
    return _format_message_tasks(tasks)

def get_message_task(db: Session, task_id: int) -> Optional[models.MessageTask]:
    return db.query(models.MessageTask).filter_by(id=task_id).first()

def update_message_task_status(db: Session, task_id: int, status: str) -> Optional[models.MessageTask]:
    row = db.query(models.MessageTask).filter_by(id=task_id).first()
    if not row:
        return None
    row.status = status
    db.commit()
    db.refresh(row)
    return row

# ── Contracts ─────────────────────────────────────────────────────────────────

def list_contracts(db: Session, company_id: int, customer_id: Optional[int] = None,
                   assigned_user_id: Optional[int] = None, skip: int = 0, limit: int = 500) -> List[models.Contract]:
    q = db.query(models.Contract).options(joinedload(models.Contract.assigned_user)).filter(models.Contract.company_id == company_id)
    if customer_id is not None:
        q = q.filter(models.Contract.customer_id == customer_id)
    if assigned_user_id is not None:
        q = q.filter(models.Contract.assigned_user_id == assigned_user_id)
    return q.order_by(models.Contract.id.desc()).offset(skip).limit(limit).all()

def get_contract(db: Session, contract_id: int) -> Optional[models.Contract]:
    return db.query(models.Contract).filter(models.Contract.id == contract_id).first()

def create_contract(db: Session, data: schemas.ContractCreate, company_id: int, assigned_user_id: int) -> models.Contract:
    row = models.Contract(
        company_id=company_id,
        customer_id=data.customer_id,
        assigned_user_id=assigned_user_id,
        vehicle_model=data.vehicle_model,
        product_type=data.product_type,
        capital=data.capital,
        contract_date=data.contract_date,
        term_months=data.term_months,
        expiry_date=data.expiry_date,
        dealer_info=data.dealer_info,
        insurance_active=data.insurance_active,
        supplies_work=data.supplies_work,
        estimate_image=data.estimate_image,
        status=data.status,
        memo=data.memo
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def update_contract(db: Session, contract_id: int, data: schemas.ContractUpdate) -> Optional[models.Contract]:
    row = get_contract(db, contract_id)
    if not row:
        return None
    patch = data.model_dump(exclude_unset=True)
    for k, v in patch.items():
        setattr(row, k, v)
        
    if "contract_date" in patch or "term_months" in patch:
        row.expiry_date = _compute_expiry(row.contract_date, row.term_months)
        
    row.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row

