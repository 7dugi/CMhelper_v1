import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import os

from automation.provider_status import ProviderStatus, ProviderEvent
from automation.quota_detector import QuotaDetector
from automation.retry_policy import RetryPolicy, RetryAction
from automation.runtime_state import RuntimeStateManager, RuntimeTaskState
from automation.models import TaskState
from automation.notifier import NotificationEvent, FileNotifier
from automation.approval_gate import ApprovalManager, ApprovalStatus

class TestH4QuotaAndRemote(unittest.TestCase):
    def test_quota_text_classification(self):
        ev = QuotaDetector.classify_provider_failure("codex", "", "Error: quota reached for this model", 1)
        self.assertEqual(ev.status, ProviderStatus.QUOTA_EXHAUSTED)
        self.assertFalse(ev.retryable)

    def test_429_classification(self):
        ev = QuotaDetector.classify_provider_failure("antigravity", "HTTP 429 Too Many Requests", "", 1)
        self.assertEqual(ev.status, ProviderStatus.RATE_LIMITED)
        self.assertTrue(ev.retryable)

    def test_normal_stderr_not_misclassified(self):
        ev = QuotaDetector.classify_provider_failure("antigravity", "", "Some normal warning message", 0)
        self.assertEqual(ev.status, ProviderStatus.AVAILABLE)

    def test_retry_limit(self):
        ev = ProviderEvent(provider="test", status=ProviderStatus.RATE_LIMITED, retryable=True)
        # First 3 attempts (0, 1, 2)
        self.assertEqual(RetryPolicy.determine_action(ev, 0), RetryAction.RETRY_IMMEDIATELY)
        self.assertEqual(RetryPolicy.determine_action(ev, 2), RetryAction.RETRY_IMMEDIATELY)
        # Attempt 3 reaches limit
        self.assertEqual(RetryPolicy.determine_action(ev, 3), RetryAction.WAIT_FOR_QUOTA)

    def test_waiting_for_quota_transition(self):
        from automation.orchestrator import Orchestrator
        from automation.models import TaskContext, Task, RiskLevel
        
        task = Task(id="t1", title="test", description="test", state=TaskState.IMPLEMENTING)
        ctx = TaskContext(task=task, repository_root=".", branch="main", head="HEAD")
        orch = Orchestrator(ctx)
        
        orch.handle_quota_exhausted()
        self.assertEqual(orch.sm.current_state, TaskState.WAITING_FOR_QUOTA)
        
        orch.resume_from_quota(TaskState.IMPLEMENTING)
        self.assertEqual(orch.sm.current_state, TaskState.IMPLEMENTING)

    def test_runtime_state_persistence_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = RuntimeStateManager(tmpdir)
            state = RuntimeTaskState(
                task_id="t1",
                state=TaskState.WAITING_FOR_QUOTA,
                provider="codex",
                resume_stage=TaskState.IMPLEMENTING
            )
            manager.save_state(state)
            
            loaded = manager.load_state()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.task_id, "t1")
            self.assertEqual(loaded.state, TaskState.WAITING_FOR_QUOTA)

    def test_suggested_resume_at_blocking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = RuntimeStateManager(tmpdir)
            future = datetime.now(timezone.utc) + timedelta(hours=1)
            state = RuntimeTaskState(
                task_id="t1",
                state=TaskState.WAITING_FOR_QUOTA,
                suggested_resume_at=future,
                resume_stage=TaskState.IMPLEMENTING
            )
            manager.save_state(state)
            
            # Should not be able to resume because time hasn't passed
            self.assertFalse(manager.can_resume())
            
            # If we pass a time strictly greater than future
            future_now = future + timedelta(minutes=1)
            self.assertTrue(manager.can_resume(now=future_now))

    def test_notifier_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "notify.log")
            notifier = FileNotifier(log_path)
            ev = NotificationEvent(event_type="WAITING", message="Out of quota", task_id="t1")
            notifier.notify(ev)
            
            with open(log_path, "r") as f:
                content = f.read()
                self.assertIn("Out of quota", content)

    def test_approval_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ApprovalManager(tmp)
            state = manager.request_approval("t1", "COMMIT", "Need commit approval")
            self.assertEqual(state.status, ApprovalStatus.PENDING)
            
            self.assertEqual(manager.check_status("t1"), ApprovalStatus.PENDING)
            
            manager.decide("t1", approved=True)
            self.assertEqual(manager.check_status("t1"), ApprovalStatus.APPROVED)

if __name__ == "__main__":
    unittest.main()
