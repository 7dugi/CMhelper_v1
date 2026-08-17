import os
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel
from .models import ApprovalAction

class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class ApprovalGateState(BaseModel):
    approval_id: str
    task_id: str
    action: str = ApprovalAction.COMMIT.value
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime
    expires_at: datetime
    decided_at: Optional[datetime] = None
    reason: str
    decision_source: Optional[str] = None
    decision_note: Optional[str] = None
    approved_sql_hash: Optional[str] = None

class ApprovalManager:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.approvals_dir = os.path.join(self.root_dir, "automation", "runtime", "approvals")
        os.makedirs(self.approvals_dir, exist_ok=True)

    def _get_path(self, approval_id: str) -> str:
        return os.path.join(self.approvals_dir, f"{approval_id}.json")
        
    def _get_task_approvals_path(self, task_id: str) -> str:
        return os.path.join(self.approvals_dir, f"task_{task_id}_index.json")

    def _save_index(self, task_id: str, approval_id: str):
        index_path = self._get_task_approvals_path(task_id)
        index = []
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                pass
        if approval_id not in index:
            index.append(approval_id)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)

    def get_task_approvals(self, task_id: str) -> List[ApprovalGateState]:
        index_path = self._get_task_approvals_path(task_id)
        if not os.path.exists(index_path):
            # Fallback for H4 legacy - check if task_id.json exists
            legacy_path = os.path.join(self.approvals_dir, f"{task_id}.json")
            if os.path.exists(legacy_path):
                try:
                    with open(legacy_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Migrating legacy to new structure if needed, or just return
                    if "approval_id" not in data:
                        data["approval_id"] = task_id
                        data["action"] = ApprovalAction.COMMIT.value
                    return [ApprovalGateState(**data)]
                except Exception:
                    pass
            return []
            
        with open(index_path, "r", encoding="utf-8") as f:
            ids = json.load(f)
            
        approvals = []
        for aid in ids:
            app = self.get_approval(aid)
            if app:
                approvals.append(app)
        return approvals

    def request_approval(self, task_id: str, action: str, reason: str, timeout_hours: int = 24, sql_hash: Optional[str] = None) -> str:
        now = datetime.now(timezone.utc)
        approval_id = str(uuid.uuid4())
        state = ApprovalGateState(
            approval_id=approval_id,
            task_id=task_id,
            action=action,
            requested_at=now,
            expires_at=now + timedelta(hours=timeout_hours),
            reason=reason,
            approved_sql_hash=sql_hash
        )
        with open(self._get_path(approval_id), "w", encoding="utf-8") as f:
            f.write(state.model_dump_json())
            
        self._save_index(task_id, approval_id)
        return approval_id

    def get_approval(self, approval_id: str) -> Optional[ApprovalGateState]:
        path = self._get_path(approval_id)
        if not os.path.exists(path):
            return None
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Legacy migration support
            if "approval_id" not in data:
                data["approval_id"] = approval_id
            if "action" not in data:
                data["action"] = ApprovalAction.COMMIT.value
            state = ApprovalGateState(**data)
            
            # Check expiration
            if state.status == ApprovalStatus.PENDING and datetime.now(timezone.utc) > state.expires_at:
                state.status = ApprovalStatus.EXPIRED
                self._save(state)
                
            return state
        except Exception:
            return None

    def check_status(self, task_id: str) -> Optional[ApprovalStatus]:
        # Legacy method for H4 control.py (returns status of the latest approval)
        apps = self.get_task_approvals(task_id)
        if not apps:
            return None
        # Return the latest requested approval's status
        latest = sorted(apps, key=lambda x: x.requested_at, reverse=True)[0]
        return latest.status

    def decide(self, identifier: str, approved: bool, source: str = "CLI", note: str = "") -> bool:
        # Identifier can be task_id (for legacy/H4 compatibility) or approval_id
        app = self.get_approval(identifier)
        if not app:
            # Try to resolve by task_id -> latest pending approval
            apps = self.get_task_approvals(identifier)
            pending_apps = [a for a in apps if a.status == ApprovalStatus.PENDING]
            if not pending_apps:
                return False
            # Pick the oldest pending to clear them out in order, or just the first
            app = pending_apps[0]
            
        # Idempotency check: if already decided, just return True if the decision matches
        if app.status != ApprovalStatus.PENDING:
            expected_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            return app.status == expected_status
            
        app.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        app.decided_at = datetime.now(timezone.utc)
        app.decision_source = source
        app.decision_note = note
        
        self._save(app)
        return True
        
    def _save(self, state: ApprovalGateState):
        with open(self._get_path(state.approval_id), "w", encoding="utf-8") as f:
            f.write(state.model_dump_json())
