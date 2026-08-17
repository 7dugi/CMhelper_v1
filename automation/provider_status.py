from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ProviderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    RATE_LIMITED = "RATE_LIMITED"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_FAILED = "AUTH_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class ProviderEvent(BaseModel):
    provider: str
    status: ProviderStatus
    message: str = ""
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    retryable: bool = False
    suggested_resume_at: Optional[datetime] = None
    raw_evidence_reference: str = ""
