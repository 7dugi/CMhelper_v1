from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ── Auth & Users ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    password_confirm: str
    invite_code: str

class UserOut(BaseModel):
    id: int
    company_id: int
    email: str
    name: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: str
    exp: int
    iat: int
    role: str
    company_id: int

# ── Field Definition ──────────────────────────────────────────────────────────

class FieldDefBase(BaseModel):
    label:      str
    field_type: str = "text"
    options:    Optional[List[str]] = None
    is_active:  bool = True
    sort_order: int = 100
    target_type: str = "contracted" # 'contracted', 'prospect', 'common'

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
            "id","name","contact","region","company","contract_car","months",
            "contract_date","contract_months","expiry_date",
            "capital","product_type","supplies_work","insurance_active","dealer_info",
            "is_prospect","is_contracted","anniversary","memo","estimate_image",
            "sent_quotes","extra","created_at","updated_at",
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
    target_type: Optional[str]      = None

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
    contact:          Optional[str]  = None
    region:           Optional[str]  = None
    company:          Optional[str]  = None
    contract_car:     Optional[str]  = None
    contract_date:    Optional[str]  = None   # YYYY-MM-DD
    contract_months:  Optional[int]  = None   # 24 / 36 / 48 / 60
    expiry_date:      Optional[str]  = None   # computed YYYY-MM-DD
    capital:          Optional[str]  = None
    product_type:     Optional[str]  = None
    supplies_work:    Optional[str]  = None
    insurance_active: bool           = False
    dealer_info:      Optional[str]  = None
    is_prospect:      int            = 0
    is_contracted:    bool           = False
    anniversary:      Optional[str]  = None
    memo:             Optional[str]  = None
    estimate_image:   Optional[str]  = None
    sent_quotes:      Optional[List[str]] = Field(default_factory=list)
    extra:            Optional[Dict[str, Any]] = Field(default_factory=dict)

class CustomerCreate(CustomerBase):
    initial_consultation: Optional[str] = None

class CustomerUpdate(BaseModel):
    name:             Optional[str]  = None
    contact:          Optional[str]  = None
    region:           Optional[str]  = None
    company:          Optional[str]  = None
    contract_car:     Optional[str]  = None
    contract_date:    Optional[str]  = None
    contract_months:  Optional[int]  = None
    capital:          Optional[str]  = None
    product_type:     Optional[str]  = None
    supplies_work:    Optional[str]  = None
    insurance_active: Optional[bool] = None
    dealer_info:      Optional[str]  = None
    is_prospect:      Optional[int]  = None
    is_contracted:    Optional[bool] = None
    anniversary:      Optional[str]  = None
    memo:             Optional[str]  = None
    estimate_image:   Optional[str]  = None
    sent_quotes:      Optional[List[str]] = None
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


# ── MessageTask ───────────────────────────────────────────────────────────────

class MessageTaskCreate(BaseModel):
    customer_id:  int
    message_text: str
    image_url:    Optional[str] = None
    scheduled_at: Optional[datetime] = None

class MessageTaskUpdate(BaseModel):
    status: str # 'pending', 'sent', 'failed'

class MessageTaskOut(BaseModel):
    id:           int
    customer_id:  int
    message_text: str
    image_url:    Optional[str] = None
    status:       str
    created_at:   datetime
    scheduled_at: Optional[datetime] = None

    # Include basic customer info for the agent
    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None

    model_config = {"from_attributes": True}
