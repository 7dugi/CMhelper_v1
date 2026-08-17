import unittest
import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from automation.models import TaskState, ApprovalAction
from automation.runtime_state import RuntimeStateManager, RuntimeTaskState
from automation.approval_gate import ApprovalManager, ApprovalStatus, ApprovalGateState
from automation.supervisor import Supervisor
from automation.health_check import ProviderHealthChecker
from automation.control import get_parser

class TestH73Remote(unittest.TestCase):
    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(__file__))
        self.runtime_mgr = RuntimeStateManager(self.root_dir)
        self.approval_mgr = ApprovalManager(self.root_dir)
        self.runtime_mgr.clear_state()
        
        # Clean up queue
        for f in self.runtime_mgr.queue_dir.glob("*.json"):
            f.unlink()

        # Clean up approvals
        for f in Path(self.approval_mgr.approvals_dir).glob("*.json"):
            f.unlink()

    def test_health_check_no_secrets(self):
        checker = ProviderHealthChecker(self.root_dir)
        status = checker.check_all()
        # Ensure it checks the required fields
        self.assertIn("DISCORD_WEBHOOK_URL_PRESENT", status)
        self.assertIn("VERCEL_AUTOMATION_BYPASS_SECRET_PRESENT", status)
        self.assertIn("CODEX_CLI_AVAILABLE", status)
        self.assertIn("AGY_CLI_AVAILABLE", status)

        # It should just be booleans, no real secret exposed
        self.assertIsInstance(status["DISCORD_WEBHOOK_URL_PRESENT"], bool)

    def test_control_parser_args(self):
        parser = get_parser()
        
        # approve should require task_id and approval_id
        args = parser.parse_args(["approve", "TASK-123", "APP-456"])
        self.assertEqual(args.command, "approve")
        self.assertEqual(args.task_id, "TASK-123")
        self.assertEqual(args.approval_id, "APP-456")

        args = parser.parse_args(["reject", "TASK-123", "APP-456"])
        self.assertEqual(args.command, "reject")
        self.assertEqual(args.task_id, "TASK-123")
        self.assertEqual(args.approval_id, "APP-456")

    def test_supervisor_auto_resume(self):
        # Create a task waiting for approval
        state = RuntimeTaskState(
            task_id="TASK-RESUME-1",
            state=TaskState.WAITING_FOR_USER_APPROVAL,
            resume_stage=TaskState.COMMITTING,
            blocking_approval_id="APP-RESUME-1",
            blocking_approval_action=ApprovalAction.COMMIT.value
        )
        self.runtime_mgr.save_state(state)
        
        # Create the pending approval
        self.approval_mgr.request_approval("TASK-RESUME-1", ApprovalAction.COMMIT.value, "Testing")
        # Overwrite ID for test
        app = self.approval_mgr.get_task_approvals("TASK-RESUME-1")[0]
        app.approval_id = "APP-RESUME-1"
        self.approval_mgr._save(app)

        # Not approved yet. Loop should do nothing.
        sup = Supervisor(self.root_dir)
        sup.loop_once()
        s2 = self.runtime_mgr.load_state()
        self.assertEqual(s2.state, TaskState.WAITING_FOR_USER_APPROVAL)

        # Now approve it
        self.approval_mgr.decide("APP-RESUME-1", approved=True)

        # Loop should resume
        sup.loop_once()
        s3 = self.runtime_mgr.load_state()
        # loop_once calls _run_worker which is mocked or synchronous. But it changes state first!
        self.assertIn(s3.state, [TaskState.COMMITTING, TaskState.RESUMING])

    def test_unrelated_pending_approval_does_not_block(self):
        # Task is blocked by APP-1
        state = RuntimeTaskState(
            task_id="TASK-RESUME-2",
            state=TaskState.WAITING_FOR_USER_APPROVAL,
            resume_stage=TaskState.COMMITTING,
            blocking_approval_id="APP-1",
            blocking_approval_action=ApprovalAction.COMMIT.value
        )
        self.runtime_mgr.save_state(state)
        
        # Create two approvals: APP-1 (APPROVED) and APP-2 (PENDING)
        app1 = ApprovalGateState(
            approval_id="APP-1",
            task_id="TASK-RESUME-2",
            action=ApprovalAction.COMMIT.value,
            status=ApprovalStatus.APPROVED,
            requested_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="1"
        )
        app2 = ApprovalGateState(
            approval_id="APP-2",
            task_id="TASK-RESUME-2",
            action=ApprovalAction.PUSH.value,
            status=ApprovalStatus.PENDING,
            requested_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="2"
        )
        self.approval_mgr._save(app1)
        self.approval_mgr._save(app2)
        self.approval_mgr._save_index("TASK-RESUME-2", "APP-1")
        self.approval_mgr._save_index("TASK-RESUME-2", "APP-2")

        sup = Supervisor(self.root_dir)
        sup.loop_once()
        
        s2 = self.runtime_mgr.load_state()
        # Because APP-1 is APPROVED, it should transition, despite APP-2 being PENDING
        self.assertIn(s2.state, [TaskState.COMMITTING, TaskState.RESUMING])

    def test_rejected_blocking_approval(self):
        state = RuntimeTaskState(
            task_id="TASK-REJECT",
            state=TaskState.WAITING_FOR_USER_APPROVAL,
            resume_stage=TaskState.COMMITTING,
            blocking_approval_id="APP-REJ",
            blocking_approval_action=ApprovalAction.COMMIT.value
        )
        self.runtime_mgr.save_state(state)

        app1 = ApprovalGateState(
            approval_id="APP-REJ",
            task_id="TASK-REJECT",
            action=ApprovalAction.COMMIT.value,
            status=ApprovalStatus.REJECTED,
            requested_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="1"
        )
        self.approval_mgr._save(app1)
        self.approval_mgr._save_index("TASK-REJECT", "APP-REJ")

        sup = Supervisor(self.root_dir)
        sup.loop_once()
        s2 = self.runtime_mgr.load_state()
        self.assertEqual(s2.state, TaskState.REJECTED_BY_USER)

    def test_startup_recovery_does_not_mutate_safe_states(self):
        state = RuntimeTaskState(
            task_id="TASK-SAFE",
            state=TaskState.QUEUED
        )
        self.runtime_mgr.save_state(state)
        sup = Supervisor(self.root_dir)
        # Should not crash it
        sup._handle_crash_recovery(state)
        s2 = self.runtime_mgr.load_state()
        self.assertEqual(s2.state, TaskState.QUEUED)
        
        # Test waiting for quota
        state.state = TaskState.WAITING_FOR_QUOTA
        self.runtime_mgr.save_state(state)
        sup._handle_crash_recovery(state)
        s3 = self.runtime_mgr.load_state()
        self.assertEqual(s3.state, TaskState.WAITING_FOR_QUOTA)

if __name__ == '__main__':
    unittest.main()
