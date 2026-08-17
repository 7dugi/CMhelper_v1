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

class TaskComplexity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ModelRole(str, Enum):
    PLANNER = "PLANNER"
    IMPLEMENTER = "IMPLEMENTER"
    REVIEWER = "REVIEWER"

class TaskState(str, Enum):
    NEW = "NEW"
    PRE_FLIGHT = "PRE_FLIGHT"
    CONTEXT_LOADING = "CONTEXT_LOADING"
    QUEUED = "QUEUED"
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    DESIGNING = "DESIGNING"
    IMPLEMENTING = "IMPLEMENTING"
    REVIEWING = "REVIEWING"
    REVISING = "REVISING"
    VALIDATING = "VALIDATING"
    TESTING = "TESTING"
    BUILDING = "BUILDING"
    DB_INSPECTION = "DB_INSPECTION"
    PREVIEW_DEPLOY = "PREVIEW_DEPLOY"
    BROWSER_QA_PLANNING = "BROWSER_QA_PLANNING"
    BROWSER_QA_EXECUTION = "BROWSER_QA_EXECUTION"
    FINAL_REVIEW = "FINAL_REVIEW"
    NEED_USER_DECISION = "NEED_USER_DECISION"
    WAITING_FOR_USER_APPROVAL = "WAITING_FOR_USER_APPROVAL"
    APPROVED_TO_COMMIT = "APPROVED_TO_COMMIT"
    REJECTED_BY_USER = "REJECTED_BY_USER"
    WAITING_FOR_QUOTA = "WAITING_FOR_QUOTA"
    RESUMING = "RESUMING"
    PAUSED = "PAUSED"
    FAILED_STALLED = "FAILED_STALLED"
    READY_TO_COMMIT = "READY_TO_COMMIT"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    PUSHING = "PUSHING"
    PUSHED = "PUSHED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
class PushPolicy(str, Enum):
    APPROVE_COMMIT_ONLY = "APPROVE_COMMIT_ONLY"
    APPROVE_COMMIT_AND_PUSH = "APPROVE_COMMIT_AND_PUSH"

class ApprovalAction(str, Enum):
    COMMIT = "COMMIT"
    PUSH = "PUSH"
    DEPLOY = "DEPLOY"
    DATABASE_WRITE = "DATABASE_WRITE"
    DATABASE_DESTRUCTIVE_WRITE = "DATABASE_DESTRUCTIVE_WRITE"

class SupabaseAccessMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    WRITE_PROPOSED = "WRITE_PROPOSED"
    WRITE_APPROVED = "WRITE_APPROVED"

class VercelAccessMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    PREVIEW_DEPLOY = "PREVIEW_DEPLOY"
    PRODUCTION_DEPLOY = "PRODUCTION_DEPLOY"

class VercelResult(BaseModel):
    deployment_id: Optional[str] = None
    url: Optional[str] = None
    status: str = "UNKNOWN"
    created_at: Optional[int] = None
    error_reason: Optional[str] = None
    is_production: bool = False

class BrowserQAStep(BaseModel):
    action: str
    selector_or_target: Optional[str] = None
    expected: Optional[str] = None
    timeout: int = 5000
    screenshot_after: bool = False

class BrowserQAScenario(BaseModel):
    scenario_id: str
    name: str
    description: str
    start_url: str
    risk: str = "SAFE_READ" # SAFE_READ, SAFE_INTERACTION, MUTATING_INTERACTION
    requires_auth: bool = False
    is_mobile: bool = False
    steps: List[BrowserQAStep] = Field(default_factory=list)

class StepResult(BaseModel):
    action: str
    status: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    screenshot: Optional[str] = None
    error: Optional[str] = None

class BrowserQAResult(BaseModel):
    scenario_id: str
    status: str = "NOT_RUN"
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    steps: List[StepResult] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)
    console_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)
    final_url: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)

class FutureEvents:
    # Supabase Event Contract
    DB_INSPECTION_STARTED = "DB_INSPECTION_STARTED"
    DB_INSPECTION_COMPLETED = "DB_INSPECTION_COMPLETED"
    DB_INSPECTION_FAILED = "DB_INSPECTION_FAILED"
    DB_WRITE_APPROVAL_REQUIRED = "DB_WRITE_APPROVAL_REQUIRED"
    DB_WRITE_APPROVED = "DB_WRITE_APPROVED"
    DB_WRITE_REJECTED = "DB_WRITE_REJECTED"
    DB_WRITE_EXECUTED = "DB_WRITE_EXECUTED"
    DB_WRITE_FAILED = "DB_WRITE_FAILED"
    
    # H6 Vercel & Browser QA Events
    DEPLOY_STARTED = "DEPLOY_STARTED"
    DEPLOY_COMPLETED = "DEPLOY_COMPLETED"
    DEPLOY_FAILED = "DEPLOY_FAILED"
    
    # Browser QA Event Contract
    BROWSER_QA_STARTED = "BROWSER_QA_STARTED"
    BROWSER_QA_STEP = "BROWSER_QA_STEP"
    BROWSER_QA_PASS = "BROWSER_QA_PASS"
    BROWSER_QA_FAILED = "BROWSER_QA_FAILED"
    SCREENSHOT_CAPTURED = "SCREENSHOT_CAPTURED"
    CONSOLE_ERROR = "CONSOLE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"

class DatabaseEvidence(BaseModel):
    project_ref: str
    connection_method: str
    inspection_timestamp: datetime = Field(default_factory=datetime.utcnow)
    schemas: List[str] = Field(default_factory=list)
    tables: List[str] = Field(default_factory=list)
    columns: str = "UNKNOWN"
    primary_keys: str = "UNKNOWN"
    indexes: str = "UNKNOWN"
    foreign_keys: str = "UNKNOWN"
    rls_enabled_tables: str = "UNKNOWN"
    policies: str = "UNKNOWN"
    migration_state: str = "UNKNOWN"
    warnings: List[str] = Field(default_factory=list)

class DatabaseChangeProposal(BaseModel):
    proposal_id: str
    task_id: str
    project_ref: str
    description: str
    risk: str # READ_ONLY, WRITE, DESTRUCTIVE
    approval_action: str = "DATABASE_WRITE"
    affected_objects: List[str] = Field(default_factory=list)
    migration_sql_reference: str
    sql_hash: str
    rollback_strategy: Optional[str] = None
    preconditions: List[str] = Field(default_factory=list)
    post_validation: List[str] = Field(default_factory=list)
    requires_approval: bool = True

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
    requested_by: str = "Anonymous"
    priority: str = "NORMAL"
    expected_branch: Optional[str] = None
    requires_db: bool = False
    requires_ui_qa: bool = False
    allowed_mutation_paths: List[str] = Field(default_factory=list)
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
