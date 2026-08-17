import unittest
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from automation.audit_logger import AuditLogger
from automation.notifier import NotificationEvent, DiscordNotifier, FileNotifier, NotificationSeverity
from automation.secret_masker import SecretMasker
from automation.approval_gate import ApprovalManager, ApprovalStatus
from automation.runtime_state import RuntimeStateManager, RuntimeTaskState
from automation.models import TaskState, PushPolicy, ReviewStatus
from automation.git_executor import SafeGitExecutor, GitExecutionError

class TestH4_3_AuditAndGit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = self.temp_dir.name
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_secret_masker(self):
        text = "My API_KEY='sk-1234567890abcdef' and token: abcdef123456 and DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123/abc"
        masked = SecretMasker.mask(text)
        self.assertNotIn("1234567890abcdef", masked)
        self.assertNotIn("abcdef123456", masked)
        self.assertNotIn("https://discord.com/api/webhooks/123/abc", masked)
        self.assertIn("sk***", masked) # simplified check

    def test_local_audit_append(self):
        # Create a mock PROJECT_ROOT to not pollute actual root
        with patch('automation.audit_logger.PROJECT_ROOT', self.test_dir):
            audit = AuditLogger("test_task")
            audit.log_event("TASK_STARTED", {"foo": "bar"})
            audit.log_event("PLAN_CREATED", {"plan": "secret_API_KEY=12345678"})
            
            with open(audit.events_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 2)
                e1 = json.loads(lines[0])
                e2 = json.loads(lines[1])
                self.assertEqual(e1["type"], "TASK_STARTED")
                self.assertEqual(e2["type"], "PLAN_CREATED")
                self.assertNotIn("12345678", lines[1])

    @patch('urllib.request.urlopen')
    def test_discord_success(self, mock_urlopen):
        notifier = DiscordNotifier("http://fake.discord")
        event = NotificationEvent(event_type="INFO", message="Test", task_id="t1")
        notifier.notify(event)
        mock_urlopen.assert_called_once()

    @patch('urllib.request.urlopen')
    @patch('automation.audit_logger.AuditLogger.log_event')
    def test_discord_failure_fallback(self, mock_log_event, mock_urlopen):
        mock_urlopen.side_effect = Exception("Network Error")
        notifier = DiscordNotifier("http://fake.discord")
        event = NotificationEvent(event_type="TEST_EVENT", message="Test", task_id="t1")
        
        # It should not raise an exception
        notifier.notify(event)
        
        # It should log AUDIT_DELIVERY_FAILED
        mock_log_event.assert_called_with("AUDIT_DELIVERY_FAILED", {
            "reason": "Network Error",
            "url": "***",
            "original_event_type": "TEST_EVENT"
        })

    def test_approval_idempotency_and_reject(self):
        manager = ApprovalManager(self.test_dir)
        manager.request_approval("t1", "COMMIT", "Reason")
        
        # Idempotent approve
        self.assertTrue(manager.decide("t1", True))
        self.assertFalse(manager.decide("t1", True))
        
        manager.request_approval("t2", "COMMIT", "Reason")
        self.assertTrue(manager.decide("t2", False))
        self.assertEqual(manager.check_status("t2"), ApprovalStatus.REJECTED)

    def test_safe_git_commit_gate(self):
        git = SafeGitExecutor(self.test_dir)
        # Mock status and branch
        git.status = MagicMock(return_value=" M automation/main.py")
        git.get_current_branch = MagicMock(return_value="feature/dev")
        
        # All pass
        self.assertTrue(git.check_commit_gate(
            "APPROVED", ReviewStatus.PASS, "PASS", "PASS", True, True, "feature/dev", ["automation/main.py"]
        ))
        
        # Fail without approval
        self.assertFalse(git.check_commit_gate(
            "PENDING", ReviewStatus.PASS, "PASS", "PASS", True, True, "feature/dev", ["automation/main.py"]
        ))

        # Fail when Review != PASS
        self.assertFalse(git.check_commit_gate(
            "APPROVED", ReviewStatus.REVISE, "PASS", "PASS", True, True, "feature/dev", ["automation/main.py"]
        ))
        
        # Fail on unexpected mutation
        git.status = MagicMock(return_value=" M forbidden.py")
        self.assertFalse(git.check_commit_gate(
            "APPROVED", ReviewStatus.PASS, "PASS", "PASS", True, True, "feature/dev", ["automation/main.py"]
        ))

    @patch('subprocess.run')
    def test_git_push_policy(self, mock_run):
        git = SafeGitExecutor(self.test_dir)
        git.get_current_branch = MagicMock(return_value="main")
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        
        git.push()
        mock_run.assert_called_with(["git", "push", "origin", "main"], cwd=self.test_dir, capture_output=True, text=True)

if __name__ == '__main__':
    unittest.main()
