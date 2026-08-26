from typing import Optional
from datetime import datetime, timezone
import hashlib

from .models import SupabaseAccessMode, DatabaseChangeProposal, ApprovalAction
from .approval_gate import ApprovalManager, ApprovalStatus
from .adapters.supabase_adapter import SupabaseAdapter

class DBConnectionError(Exception):
    pass

class DBAuthError(DBConnectionError):
    pass

class DBQuotaError(DBConnectionError):
    pass

class DBWriteBlockError(Exception):
    pass

class DBWriteExecutor:
    def __init__(self, adapter: SupabaseAdapter, approval_manager: ApprovalManager):
        self.adapter = adapter
        self.approval_manager = approval_manager

    def execute_proposal(self, proposal: DatabaseChangeProposal, approval_id: str) -> bool:
        if self.adapter.mode == SupabaseAccessMode.READ_ONLY:
            if proposal.risk in ["WRITE", "DESTRUCTIVE"]:
                raise DBWriteBlockError("Blocked: READ_ONLY mode cannot execute WRITE/DESTRUCTIVE SQL")

        approval = self.approval_manager.get_approval(approval_id)
        if not approval:
            raise DBWriteBlockError("Blocked: Approval not found")

        if approval.status != ApprovalStatus.APPROVED:
            raise DBWriteBlockError("Blocked: Approval is not in APPROVED status")
            
        if approval.action not in [ApprovalAction.DATABASE_WRITE.value, ApprovalAction.DATABASE_DESTRUCTIVE_WRITE.value]:
            raise DBWriteBlockError(f"Blocked: Wrong approval action {approval.action}")

        now = datetime.now(timezone.utc)
        if approval.expires_at and now > approval.expires_at:
            raise DBWriteBlockError("Blocked: Approval has expired")
            
        if approval.approved_sql_hash != proposal.sql_hash:
            raise DBWriteBlockError("Blocked: SQL Hash mismatch")
            
        # Verify Project Ref matches
        # Assuming the proposal was created for a specific project, we should check adapter's project_ref
        # Wait, DatabaseChangeProposal doesn't have project_ref in models.py, let's add it there or just assume for now.
        # The prompt says: "DB PROPOSAL <-> APPROVAL BINDING DatabaseChangeProposal에 최소 다음 관계를 검증한다. proposal_id, task_id, project_ref, sql_hash, risk, approval_action"
        if not hasattr(proposal, "project_ref") or proposal.project_ref != self.adapter.project_ref:
            raise DBWriteBlockError("Blocked: Project Ref mismatch")
            
        # Simulate Execution successfully for H5 Mock
        return True
