from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class ReviewStatus(str, Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    NEED_USER_DECISION = "NEED_USER_DECISION"
    FAILED_STALLED = "FAILED_STALLED"

class RiskLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"

class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_RUN = "NOT_RUN"

class TaskState(str, Enum):
    NEW = "NEW"
    PRE_FLIGHT = "PRE_FLIGHT"
    CONTEXT_LOADING = "CONTEXT_LOADING"
    PLANNING = "PLANNING"
    DESIGNING = "DESIGNING"
    IMPLEMENTING = "IMPLEMENTING"
    REVIEWING = "REVIEWING"
    REVISING = "REVISING"
    VALIDATING = "VALIDATING"
    TESTING = "TESTING"
    BUILDING = "BUILDING"
    DB_VERIFY = "DB_VERIFY"
    PREVIEW_DEPLOY = "PREVIEW_DEPLOY"
    UI_VERIFY = "UI_VERIFY"
    NEED_USER_DECISION = "NEED_USER_DECISION"
    FAILED_STALLED = "FAILED_STALLED"
    READY_TO_COMMIT = "READY_TO_COMMIT"
    COMMITTING = "COMMITTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class EvidenceItem(BaseModel):
    name: str
    category: str
    required: bool = False
    status: ValidationStatus = ValidationStatus.NOT_RUN
    summary: str = ""
    source: str = ""

class AcceptanceCriterion(BaseModel):
    id: str
    description: str
    required: bool = True
    status: ValidationStatus = ValidationStatus.NOT_RUN
    evidence: Optional[EvidenceItem] = None

class Task(BaseModel):
    id: str
    title: str
    description: str
    state: TaskState = TaskState.NEW
    risk_level: RiskLevel = RiskLevel.GREEN
    designer_required: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class LoadedDocument(BaseModel):
    path: str
    exists: bool
    loaded: bool
    content: str = ""
    sha256: str = ""

class TaskContext(BaseModel):
    task: Task
    repository_root: str
    branch: str
    head: str
    governance_documents: List[str] = Field(default_factory=list)
    task_specific_documents: List[str] = Field(default_factory=list)
    loaded_documents: Dict[str, LoadedDocument] = Field(default_factory=dict)

from pydantic import BaseModel, Field, field_validator
import re

class SeniorPlan(BaseModel):
    summary: str
    scope: List[str]
    out_of_scope: List[str]
    acceptance_criteria: List[AcceptanceCriterion]
    required_validations: List[str]
    risk_level: RiskLevel
    designer_required: bool
    user_decision_required: bool
    allowed_mutation_paths: List[str] = Field(default_factory=list)

    @field_validator('required_validations')
    def validate_no_shell_commands(cls, v):
        forbidden = r'\b(git|rg|pytest|npm|ripgrep|curl|wget)\b'
        for val in v:
            if re.search(forbidden, val, re.IGNORECASE):
                raise ValueError(f"Shell commands are not allowed in required_validations. Found forbidden pattern in: {val}")
        return v

class ImplementationResult(BaseModel):
    summary: str
    changed_files: List[str] = Field(default_factory=list)
    tests: Any = ""
    build: Any = ""
    db_impact: Any = ""
    ui_impact: Any = ""
    issues: List[Any] = Field(default_factory=list)
    user_decision_required: Optional[bool] = False

class ReviewResult(BaseModel):
    status: ReviewStatus
    summary: str
    issues: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    next_instruction: str = ""
    approval_question: str = ""
    risk_level: RiskLevel = RiskLevel.GREEN

class ValidationResult(BaseModel):
    tests: ValidationStatus = ValidationStatus.NOT_RUN
    build: ValidationStatus = ValidationStatus.NOT_RUN
    database: ValidationStatus = ValidationStatus.NOT_RUN
    preview: ValidationStatus = ValidationStatus.NOT_RUN
    ui: ValidationStatus = ValidationStatus.NOT_RUN

    def all_required_passed(self, required_validations: List[str]) -> bool:
        for val in required_validations:
            status = getattr(self, val, ValidationStatus.NOT_REQUIRED)
            if status == ValidationStatus.FAIL or status == ValidationStatus.NOT_RUN:
                return False
        return True

class ApprovalRequest(BaseModel):
    reason: str
    risk_level: RiskLevel
    question: str
    details: str
    approved: bool = False

class CommandSpec(BaseModel):
    executable: str
    args: List[str]
    cwd: str
    safe_mode: bool
