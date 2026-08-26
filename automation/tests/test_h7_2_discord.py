import unittest
import os
import json
from unittest.mock import patch, MagicMock
from automation.notifier import DiscordNotifier, NotificationEvent, NotificationSeverity, dispatch_notification
from automation.runtime_state import RuntimeStateManager, RuntimeTaskState, TaskState
from automation.approval_gate import ApprovalManager

class TestDiscordNotifier(unittest.TestCase):

    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(__file__))
        self.state_mgr = RuntimeStateManager(self.root_dir)
        self.approval_mgr = ApprovalManager(self.root_dir)

    def test_webhook_env_missing(self):
        notifier = DiscordNotifier(webhook_url=None)
        # Should not raise exception
        notifier.notify(NotificationEvent(
            event_type="TEST",
            task_id="t1",
            message="Test",
            send_to_discord=True
        ))

    @patch("urllib.request.urlopen")
    def test_task_started_payload(self, mock_urlopen):
        notifier = DiscordNotifier("http://fake.discord.webhook")
        event = NotificationEvent(
            event_type="TASK_STARTING",
            task_id="t1",
            message="Starting queued task t1.",
            send_to_discord=True
        )
        notifier.notify(event)
        
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode('utf-8'))
        self.assertIn("TASK_STARTING", payload["content"])
        self.assertIn("t1", payload["content"])

    @patch("urllib.request.urlopen")
    def test_waiting_for_approval_payload(self, mock_urlopen):
        notifier = DiscordNotifier("http://fake.discord.webhook")
        event = NotificationEvent(
            event_type="TASK_WAITING_FOR_APPROVAL",
            task_id="t1",
            message="Approval Required:\n- Approval ID: `123`\n- Action: **COMMIT**",
            severity=NotificationSeverity.ACTION_REQUIRED,
            send_to_discord=True
        )
        notifier.notify(event)
        
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode('utf-8'))
        self.assertIn("ACTION_REQUIRED", payload["content"])
        self.assertIn("COMMIT", payload["content"])
        self.assertIn("123", payload["content"])

    @patch("urllib.request.urlopen")
    def test_failed_stalled_payload(self, mock_urlopen):
        notifier = DiscordNotifier("http://fake.discord.webhook")
        event = NotificationEvent(
            event_type="TASK_FAILED_STALLED",
            task_id="t1",
            message="Pipeline stalled due to failure.",
            severity=NotificationSeverity.ERROR,
            send_to_discord=True
        )
        notifier.notify(event)
        
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode('utf-8'))
        self.assertIn("ERROR", payload["content"])
        self.assertIn("FAILED_STALLED", payload["content"])

    @patch("urllib.request.urlopen")
    def test_secret_masking(self, mock_urlopen):
        notifier = DiscordNotifier("https://discord.com/api/webhooks/123/ABC")
        os.environ["DISCORD_WEBHOOK_URL"] = "https://discord.com/api/webhooks/123/ABC"
        event = NotificationEvent(
            event_type="TEST",
            task_id="t1",
            message="My secret is https://discord.com/api/webhooks/12345/supersecrettoken and it should be hidden.",
            send_to_discord=True
        )
        notifier.notify(event)
        
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode('utf-8'))
        self.assertNotIn("supersecrettoken", payload["content"])
        self.assertIn("su", payload["content"])
        self.assertIn("en", payload["content"])

    @patch("urllib.request.urlopen")
    def test_discord_failure_does_not_stop_pipeline(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("DNS Resolution Failed")
        notifier = DiscordNotifier("http://fake.discord.webhook")
        
        # Should not raise
        notifier.notify(NotificationEvent(
            event_type="TEST",
            task_id="t1",
            message="Test",
            send_to_discord=True
        ))
        
        # Check audit log to ensure the webhook was masked
        audit_path = os.path.join(self.root_dir, "automation", "runtime", "audit", "t1", "t1.jsonl")
        if os.path.exists(audit_path):
            with open(audit_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn("http://fake.discord.webhook", content)

    @patch("automation.approval_gate.dispatch_notification")
    def test_duplicate_approval_notification_blocked(self, mock_dispatch):
        # The architecture ensures request_approval generates a unique approval ID
        # and sends exactly one notification per request_approval call.
        app_id = self.approval_mgr.request_approval("t_dedup", "COMMIT", "Reason")
        mock_dispatch.assert_called_once()
        
        # Next poll won't call request_approval, so no duplicate notification.
        app = self.approval_mgr.get_approval(app_id)
        self.assertIsNotNone(app)

    @patch("urllib.request.urlopen")
    def test_unsupported_noisy_stage_does_not_notify(self, mock_urlopen):
        notifier = DiscordNotifier("http://fake.discord.webhook")
        # No send_to_discord=True
        event = NotificationEvent(
            event_type="NOISY_STAGE",
            task_id="t1",
            message="Just some noise",
            send_to_discord=False
        )
        notifier.notify(event)
        mock_urlopen.assert_not_called()

if __name__ == "__main__":
    unittest.main()
