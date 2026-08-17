import unittest
from unittest.mock import patch, MagicMock
from automation.notifier import DiscordNotifier, NotificationEvent, NotificationSeverity

class TestDiscordNotifier(unittest.TestCase):
    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_discord_notifier_user_agent(self, mock_request, mock_urlopen):
        notifier = DiscordNotifier("http://fake-webhook.local")
        event = NotificationEvent(
            event_type="TEST_EVENT",
            message="Test message",
            task_id="test_task",
            severity=NotificationSeverity.INFO,
            send_to_discord=True
        )
        
        notifier.notify(event)
        
        # Verify that Request was called with User-Agent
        self.assertTrue(mock_request.called)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "http://fake-webhook.local")
        self.assertIn("headers", kwargs)
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(kwargs["headers"]["User-Agent"], "CMhelper-Automated-Testing/1.0")
        
        # Verify urlopen was called
        self.assertTrue(mock_urlopen.called)

if __name__ == "__main__":
    unittest.main()
