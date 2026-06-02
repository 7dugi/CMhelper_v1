from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, field_validator


# ── Field Definition ──────────────────────────────────────────────────────────

class FieldDefBase(BaseModel):
    label:      str
    field_type: str = "text"
    options:    Optional[List[str]] = None
    is_active:  bool = True
    sort_order: int = 100

class FieldDefCreate(FieldDefBase):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        import re
        v = v.strip().lower()
        if not re.match(r'^[a-z][a-z0-9_]*$', v):
            raise ValueError("name must start with a letter and contain only lowercase letters, digits or underscores")
        reserved = {
            "id","name","company","contract_car","months",
            "contract_date","contract_months","expiry_date",
            "capital","supplies_work","insurance_active","dealer_info",
            "is_prospect","anniversary","memo",
            "extra","created_at","updated_at",
        }
        if v in reserved:
            raise ValueError(f"'{v}' is a reserved field name")
        return v

class FieldDefUpdate(BaseModel):
    label:      Optional[str]       = None
    field_type: Optional[str]       = None
    options:    Optional[List[str]] = None
    is_active:  Optional[bool]      = None
    sort_order: Optional[int]       = None

class FieldDefOut(FieldDefBase):
    id:        str
    name:      str
    is_system: bool
    model_config = {"from_attributes": True}


# ── Consultation ──────────────────────────────────────────────────────────────

class ConsultationCreate(BaseModel):
    notes: str

class ConsultationOut(ConsultationCreate):
    id:          int
    customer_id: int
    created_at:  datetime
    model_config = {"from_attributes": True}


# ── Customer ──────────────────────────────────────────────────────────────────

class CustomerBase(BaseModel):
    name:             str
    company:          Optional[str]  = None
    contract_car:     Optional[str]  = None
    contract_date:    Optional[str]  = None   # YYYY-MM-DD
    contract_months:  Optional[int]  = None   # 24 / 36 / 48 / 60
    expiry_date:      Optional[str]  = None   # computed YYYY-MM-DD
    capital:          Optional[str]  = None
    supplies_work:    Optional[str]  = None
    insurance_active: bool           = False
    dealer_info:      Optional[str]  = None
    is_prospect:      bool           = False
    anniversary:      Optional[str]  = None
    memo:             Optional[str]  = None
    extra:            Dict[str, Any] = {}

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name:             Optional[str]  = None
    company:          Optional[str]  = None
    contract_car:     Optional[str]  = None
    contract_date:    Optional[str]  = None
    contract_months:  Optional[int]  = None
    capital:          Optional[str]  = None
    supplies_work:    Optional[str]  = None
    insurance_active: Optional[bool] = None
    dealer_info:      Optional[str]  = None
    is_prospect:      Optional[bool] = None
    anniversary:      Optional[str]  = None
    memo:             Optional[str]  = None
    extra:            Optional[Dict[str, Any]] = None

class CustomerOut(CustomerBase):
    id:            int
    created_at:    datetime
    updated_at:    datetime
    consultations: List[ConsultationOut] = []
    model_config = {"from_attributes": True}


# ── Excel helpers ─────────────────────────────────────────────────────────────

class MappingItem(BaseModel):
    excel_col: str
    db_field:  str

class ImportResult(BaseModel):
    success: int
    skipped: int
    errors:  List[str]
