import datetime
import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import Base


class FieldDefinition(Base):
    """Stores both system-default and user-created field definitions."""
    __tablename__ = "field_definitions"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String, unique=True, nullable=False, index=True)
    label       = Column(String, nullable=False)
    field_type  = Column(String, nullable=False, default="text")
    options     = Column(JSON, nullable=True)
    is_system   = Column(Boolean, default=False, nullable=False)
    is_active   = Column(Boolean, default=True, nullable=False)
    sort_order  = Column(Integer, default=100, nullable=False)
    target_type = Column(String, default="contracted", nullable=False) # 'contracted', 'prospect', 'common'


class Customer(Base):
    """Core customer record."""
    __tablename__ = "customers"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    # ── System fixed columns ───────────────────────────────────────────────
    name             = Column(String, index=True)
    contact          = Column(String, nullable=True)
    region           = Column(String, nullable=True)
    company          = Column(String, nullable=True, index=True)
    contract_car     = Column(String, nullable=True, index=True)
    months           = Column(Integer, nullable=True)   # legacy – kept for compat
    contract_date    = Column(String, nullable=True)    # YYYY-MM-DD
    contract_months  = Column(Integer, nullable=True)   # 24 / 36 / 48 / 60
    expiry_date      = Column(String, nullable=True)    # computed YYYY-MM-DD
    capital          = Column(String, nullable=True)
    product_type     = Column(String, nullable=True)
    supplies_work    = Column(String, nullable=True)
    insurance_active = Column(Boolean, default=False)
    dealer_info      = Column(String, nullable=True)
    is_prospect      = Column(Integer, default=0)
    is_contracted    = Column(Boolean, default=False)
    anniversary      = Column(String, nullable=True)
    memo             = Column(String, nullable=True)
    estimate_image   = Column(String, nullable=True)
    sent_quotes      = Column(JSON, default=list, nullable=True) # List of image URLs
    # ── Flexible bag for user-added fields ────────────────────────────────
    extra            = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow, nullable=False)

    consultations = relationship("Consultation", back_populates="customer",
                                 cascade="all, delete-orphan",
                                 order_by="Consultation.id.desc()")


class Consultation(Base):
    __tablename__ = "consultations"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"),
                         nullable=False)
    notes       = Column(String, nullable=False)
    created_at  = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    customer = relationship("Customer", back_populates="consultations")


class MessageTask(Base):
    __tablename__ = "message_tasks"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    customer_id  = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    message_text = Column(String, nullable=False)
    image_url    = Column(String, nullable=True)
    status       = Column(String, default="RESERVED", nullable=False) # 'RESERVED', 'PROCESSING', 'RECOVERY', 'SUCCESS', 'FAILED', 'CANCELLED'
    created_at   = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)

    locked_by    = Column(String, nullable=True)
    locked_at    = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    retry_count  = Column(Integer, default=0, nullable=False)
    error_code   = Column(String, nullable=True)

    customer = relationship("Customer")
