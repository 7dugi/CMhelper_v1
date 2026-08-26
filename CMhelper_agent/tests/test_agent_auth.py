"""CMhelper PC Agent - Authentication and Fail-Closed Unit Tests

Uses exclusively synthetic/fake data (fake credentials, fake tokens, fake customer records).
Tests:
1. Successful login and in-memory-only token retention.
2. Login rejection (401 invalid credentials, 403 inactive account).
3. Authenticated requests attaching Bearer token.
4. 401/403 fail-closed invalidation of in-memory token.
5. Prevention of false success when server status update fails.
6. Immediate password widget clearing on login submission.
7. Unauthenticated action blocking.
8. Secret masking in representations and exceptions.
"""
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure CMhelper_agent is in sys.path
AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from api_client import AgentApiClient, AgentApiError, AuthenticationError


class TestAgentApiClientAuth(unittest.TestCase):
    def setUp(self):
        self.base_url = "http://fake-server.local/api"
        self.mock_session = MagicMock()
        self.client = AgentApiClient(base_url=self.base_url, session=self.mock_session)

    def test_initial_state_is_unauthenticated(self):
        self.assertFalse(self.client.is_authenticated())
        self.assertIsNone(self.client._access_token)

    def test_unauthenticated_requests_fail_closed_before_network(self):
        with self.assertRaises(AuthenticationError):
            self.client.get_pending_messages()
        with self.assertRaises(AuthenticationError):
            self.client.update_message_status(101, "sent")
        with self.assertRaises(AuthenticationError):
            self.client.cancel_pending_messages()
        # Ensure no network requests were attempted
        self.mock_session.get.assert_not_called()
        self.mock_session.put.assert_not_called()
        self.mock_session.delete.assert_not_called()

    def test_login_success_stores_token_in_process_memory_only(self):
        fake_token = "fake-jwt-token-xyz.header.payload"
        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"access_token": fake_token, "token_type": "bearer"}
        self.mock_session.post.return_value = fake_response

        success = self.client.login("fake_manager@example.com", "fake_password_1234")
        self.assertTrue(success)
        self.assertTrue(self.client.is_authenticated())
        self.assertEqual(self.client._access_token, fake_token)

        # Verify password is not saved as an attribute on the client instance
        self.assertFalse(hasattr(self.client, "password"))
        self.assertFalse(hasattr(self.client, "_password"))

        # Verify request parameters
        self.mock_session.post.assert_called_once_with(
            f"{self.base_url}/auth/login",
            json={"email": "fake_manager@example.com", "password": "fake_password_1234"},
            timeout=15,
        )

    def test_login_rejection_401_invalidates_auth_and_raises(self):
        fake_response = MagicMock(status_code=401)
        fake_response.json.return_value = {"detail": "Invalid credentials"}
        self.mock_session.post.return_value = fake_response

        with self.assertRaises(AuthenticationError) as ctx:
            self.client.login("fake_user@example.com", "wrong_password_9999")

        self.assertFalse(self.client.is_authenticated())
        self.assertIsNone(self.client._access_token)
        self.assertIn("401", str(ctx.exception))
        # Ensure password is not present in exception string
        self.assertNotIn("wrong_password_9999", str(ctx.exception))

    def test_login_rejection_403_inactive_raises_and_clears_auth(self):
        fake_response = MagicMock(status_code=403)
        fake_response.json.return_value = {"detail": "비활성화된 계정입니다."}
        self.mock_session.post.return_value = fake_response

        with self.assertRaises(AuthenticationError):
            self.client.login("inactive_user@example.com", "fake_pwd_123")

        self.assertFalse(self.client.is_authenticated())
        self.assertIsNone(self.client._access_token)

    def test_authenticated_get_pending_messages_sends_bearer_header(self):
        self.client._access_token = "fake-active-jwt-token"
        fake_tasks = [
            {"id": 201, "customer_name": "홍길동", "customer_contact": "010-0000-0000", "message_text": "테스트 발송"},
            {"id": 202, "customer_name": "이순신", "customer_contact": "010-1111-1111", "message_text": "테스트 발송 2"},
        ]
        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = fake_tasks
        self.mock_session.get.return_value = fake_response

        result = self.client.get_pending_messages()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 201)

        self.mock_session.get.assert_called_once_with(
            f"{self.base_url}/messages/pending",
            headers={"Authorization": "Bearer fake-active-jwt-token"},
            timeout=15,
        )

    def test_get_pending_messages_401_clears_token_and_fails_closed(self):
        self.client._access_token = "fake-expired-jwt-token"
        fake_response = MagicMock(status_code=401)
        self.mock_session.get.return_value = fake_response

        with self.assertRaises(AuthenticationError):
            self.client.get_pending_messages()

        self.assertFalse(self.client.is_authenticated())
        self.assertIsNone(self.client._access_token)

    def test_get_pending_messages_403_clears_token_and_fails_closed(self):
        self.client._access_token = "fake-forbidden-jwt-token"
        fake_response = MagicMock(status_code=403)
        self.mock_session.get.return_value = fake_response

        with self.assertRaises(AuthenticationError):
            self.client.get_pending_messages()

        self.assertFalse(self.client.is_authenticated())
        self.assertIsNone(self.client._access_token)

    def test_update_message_status_authenticated_success(self):
        self.client._access_token = "fake-active-jwt-token"
        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"id": 201, "status": "sent"}
        self.mock_session.put.return_value = fake_response

        result = self.client.update_message_status(201, "sent")
        self.assertEqual(result["status"], "sent")

        self.mock_session.put.assert_called_once_with(
            f"{self.base_url}/messages/201/status",
            json={"status": "sent"},
            headers={"Authorization": "Bearer fake-active-jwt-token"},
            timeout=15,
        )

    def test_update_message_status_401_invalidates_auth(self):
        self.client._access_token = "fake-active-jwt-token"
        fake_response = MagicMock(status_code=401)
        self.mock_session.put.return_value = fake_response

        with self.assertRaises(AuthenticationError):
            self.client.update_message_status(201, "sent")

        self.assertFalse(self.client.is_authenticated())
        self.assertIsNone(self.client._access_token)

    def test_update_message_status_server_failure_prevents_false_success(self):
        self.client._access_token = "fake-active-jwt-token"
        fake_response = MagicMock(status_code=500)
        self.mock_session.put.return_value = fake_response

        with self.assertRaises(AgentApiError):
            self.client.update_message_status(201, "sent")

        # Token remains intact on 500 (server transient error, not auth invalidation)
        self.assertTrue(self.client.is_authenticated())

    def test_cancel_pending_messages_authenticated_success(self):
        self.client._access_token = "fake-active-jwt-token"
        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"detail": "All pending messages cancelled"}
        self.mock_session.delete.return_value = fake_response

        result = self.client.cancel_pending_messages()
        self.assertEqual(result["detail"], "All pending messages cancelled")

        self.mock_session.delete.assert_called_once_with(
            f"{self.base_url}/messages/pending",
            headers={"Authorization": "Bearer fake-active-jwt-token"},
            timeout=15,
        )

    def test_cancel_pending_messages_401_fails_closed(self):
        self.client._access_token = "fake-active-jwt-token"
        fake_response = MagicMock(status_code=401)
        self.mock_session.delete.return_value = fake_response

        with self.assertRaises(AuthenticationError):
            self.client.cancel_pending_messages()

        self.assertFalse(self.client.is_authenticated())
        self.assertIsNone(self.client._access_token)

    def test_repr_and_str_never_leak_token_or_secrets(self):
        secret_token = "very-sensitive-jwt-token-value-98765"
        self.client._access_token = secret_token

        repr_str = repr(self.client)
        str_val = str(self.client)

        self.assertNotIn(secret_token, repr_str)
        self.assertNotIn(secret_token, str_val)
        self.assertIn("authenticated=True", repr_str)


class TestAgentAuthWorkflow(unittest.TestCase):
    def test_clear_auth_resets_token(self):
        client = AgentApiClient("http://fake-server/api")
        client._access_token = "fake-token"
        self.assertTrue(client.is_authenticated())

        client.clear_auth()
        self.assertFalse(client.is_authenticated())
        self.assertIsNone(client._access_token)


class TestAgentUIAuthAndErrorHandling(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from agent import CMHelperAgent
        self.CMHelperAgent = CMHelperAgent
        self.tk = tk

    def test_password_entry_cleared_immediately_on_login(self):
        agent = MagicMock()
        agent.email_entry = MagicMock()
        agent.email_entry.get.return_value = "manager@example.com"
        agent.password_entry = MagicMock()
        agent.password_entry.get.return_value = "secret_password_1234"
        agent.login_btn = MagicMock()
        agent.auth_status_var = MagicMock()

        with patch("threading.Thread") as mock_thread:
            self.CMHelperAgent.handle_login(agent)

            # Password widget must be deleted immediately upon submission
            agent.password_entry.delete.assert_called_once_with(0, self.tk.END)
            mock_thread.assert_called_once()

    def test_cancel_selected_preserves_item_on_server_failure(self):
        agent = MagicMock()
        agent.tasks_to_send = [{"id": 301, "customer_name": "홍길동"}]
        agent.tree = MagicMock()
        agent.tree.item.return_value = ("301",)
        agent.api_client = MagicMock()
        agent.api_client.update_message_status.side_effect = AgentApiError("Server error 500")

        self.CMHelperAgent._run_cancel_selected(agent, ["item_row_1"])

        # Treeview row must NOT be deleted and task must NOT be removed from tasks_to_send
        agent.tree.delete.assert_not_called()
        self.assertEqual(len(agent.tasks_to_send), 1)
        self.assertEqual(agent.tasks_to_send[0]["id"], 301)

    def test_cancel_selected_halts_and_invalidates_on_auth_error(self):
        agent = MagicMock()
        agent.tasks_to_send = [{"id": 301, "customer_name": "홍길동"}]
        agent.tree = MagicMock()
        agent.tree.item.return_value = ("301",)
        agent.api_client = MagicMock()
        agent.api_client.update_message_status.side_effect = AuthenticationError("HTTP 401")

        self.CMHelperAgent._run_cancel_selected(agent, ["item_row_1"])

        agent.tree.delete.assert_not_called()
        agent._handle_auth_invalidation.assert_called_once_with("인증 만료")
        self.assertEqual(len(agent.tasks_to_send), 1)

    def test_cancel_selected_success_removes_item_from_tree_and_tasks(self):
        agent = MagicMock()
        agent.tasks_to_send = [{"id": 301, "customer_name": "홍길동"}]
        agent.tree = MagicMock()
        agent.tree.item.return_value = ("301",)
        agent.api_client = MagicMock()
        agent.api_client.update_message_status.return_value = {"id": 301, "status": "failed"}

        self.CMHelperAgent._run_cancel_selected(agent, ["item_row_1"])

        agent.tree.delete.assert_called_once_with("item_row_1")
        self.assertEqual(len(agent.tasks_to_send), 0)

    def test_unauthenticated_actions_are_blocked(self):
        agent = MagicMock()
        agent.is_running = False
        agent.tasks_to_send = [{"id": 301, "customer_name": "홍길동"}]
        agent.api_client = MagicMock()
        agent.api_client.is_authenticated.return_value = False

        # load_queue blocked
        with patch("threading.Thread") as mock_thread:
            self.CMHelperAgent.load_queue(agent)
            mock_thread.assert_not_called()

        # start_sending blocked
        with patch("threading.Thread") as mock_thread:
            self.CMHelperAgent.start_sending(agent)
            mock_thread.assert_not_called()

        # cancel_queue blocked
        with patch("threading.Thread") as mock_thread:
            self.CMHelperAgent.cancel_queue(agent)
            mock_thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
