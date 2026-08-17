from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from pathlib import Path

class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class ApprovalGateState(BaseModel):
    task_id: str
    action: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    reason: str = ""

class ApprovalManager:
    def __init__(self, root_dir: str):
        self.approvals_dir = Path(root_dir) / "automation" / "runtime" / "approvals"
        self.approvals_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, task_id: str) -> Path:
        return self.approvals_dir / f"{task_id}.json"

    def _save(self, state: ApprovalGateState):
        p = self._get_path(state.task_id)
        temp_file = p.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(state.model_dump_json(indent=2))
                f.flush()
                import os
                os.fsync(f.fileno())
            temp_file.replace(p)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e

    def _load(self, task_id: str) -> Optional[ApprovalGateState]:
        p = self._get_path(task_id)
        if not p.exists():
            return None
        try:
            import json
            with open(p, 'r', encoding='utf-8') as f:
                return ApprovalGateState(**json.load(f))
        except Exception:
            return None

    def request_approval(self, task_id: str, action: str, reason: str = "") -> ApprovalGateState:
        state = ApprovalGateState(
            task_id=task_id,
            action=action,
            reason=reason
        )
        self._save(state)
        return state

    def check_status(self, task_id: str) -> Optional[ApprovalStatus]:
        state = self._load(task_id)
        if state:
            if state.status == ApprovalStatus.PENDING and state.expires_at and datetime.now(timezone.utc) > state.expires_at:
                state.status = ApprovalStatus.EXPIRED
                self._save(state)
            return state.status
        return None

    def decide(self, task_id: str, approved: bool):
        state = self._load(task_id)
        if state and state.status == ApprovalStatus.PENDING:
            state.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            state.decided_at = datetime.utcnow()
            self._save(state)
            return True
        return False
