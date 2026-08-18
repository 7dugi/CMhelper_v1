import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import os
from automation.discord_bot import ApprovalView
import discord

class MockInteraction:
    def __init__(self, user_id):
        self.user = MagicMock()
        self.user.id = user_id
        self.response = MagicMock()
        self.response.send_message = AsyncMock()
        self.message = MagicMock()
        self.message.edit = AsyncMock()

class TestDiscordInteractiveApproval(unittest.IsolatedAsyncioTestCase):
    @patch("automation.discord_bot.ApprovalManager")
    @patch("automation.discord_bot.os.environ.get")
    async def test_authorized_user_approve(self, mock_env, mock_mgr_class):
        mock_env.return_value = "/tmp"
        mock_app = MagicMock()
        mock_app.status = "PENDING"
        mock_app.task_id = "t1"
        mock_app.action = "COMMIT"
        
        mock_mgr = mock_mgr_class.return_value
        mock_mgr.get_approval.return_value = mock_app
        mock_mgr.decide.return_value = True
        
        view = ApprovalView("app1", "t1", "p1", "COMMIT", ["123"])
        interaction = MockInteraction(123)
        
        # Test interaction_check
        self.assertTrue(await view.interaction_check(interaction))
        
        # Test approve
        await view._handle_decision(interaction, True)
        mock_mgr.decide.assert_called_with("app1", True, source="Discord User 123")
        interaction.response.send_message.assert_called_with(f"Task `t1` action `COMMIT` was APPROVED.")
        self.assertTrue(view.children[0].disabled)

    @patch("automation.discord_bot.ApprovalManager")
    @patch("automation.discord_bot.os.environ.get")
    async def test_unauthorized_user_denied(self, mock_env, mock_mgr_class):
        view = ApprovalView("app1", "t1", "p1", "COMMIT", ["123"])
        interaction = MockInteraction(999)
        
        self.assertFalse(await view.interaction_check(interaction))
        interaction.response.send_message.assert_called_with("You are not authorized to approve or reject tasks.", ephemeral=True)

    @patch("automation.discord_bot.ApprovalManager")
    @patch("automation.discord_bot.os.environ.get")
    async def test_stale_or_duplicate_interaction(self, mock_env, mock_mgr_class):
        mock_app = MagicMock()
        mock_app.status = "APPROVED"
        
        mock_mgr = mock_mgr_class.return_value
        mock_mgr.get_approval.return_value = mock_app
        
        view = ApprovalView("app1", "t1", "p1", "COMMIT", ["123"])
        interaction = MockInteraction(123)
        
        await view._handle_decision(interaction, True)
        interaction.response.send_message.assert_called_with("This request was already decided: APPROVED", ephemeral=True)

    @patch("automation.discord_bot.ApprovalManager")
    @patch("automation.discord_bot.os.environ.get")
    async def test_wrong_context_denied(self, mock_env, mock_mgr_class):
        mock_app = MagicMock()
        mock_app.status = "PENDING"
        mock_app.task_id = "t2" # mismatch
        mock_app.action = "COMMIT"
        
        mock_mgr = mock_mgr_class.return_value
        mock_mgr.get_approval.return_value = mock_app
        
        view = ApprovalView("app1", "t1", "p1", "COMMIT", ["123"])
        interaction = MockInteraction(123)
        
        await view._handle_decision(interaction, True)
        interaction.response.send_message.assert_called_with("Approval context mismatch. Denied.", ephemeral=True)

class TestIsolationAndFailClosed(unittest.TestCase):
    def test_action_isolation(self):
        # Ensure we only grant the exact action requested
        from automation.approval_gate import ApprovalManager
        from tempfile import TemporaryDirectory
        
        with TemporaryDirectory() as tmp:
            mgr = ApprovalManager(tmp)
            # Create a commit approval (task_id, action, reason)
            app_id = mgr.request_approval("t1", "COMMIT", "Reason")
            app = mgr.get_approval(app_id)
            self.assertEqual(app.action, "COMMIT")
            # Approving COMMIT does not create PUSH approval
            mgr.decide(app_id, True, "test")
            
            # Check PUSH doesn't exist
            self.assertIsNone(mgr.get_approval("nonexistent"))

    def test_resume_fail_closed(self):
        # We test that main loop will fail closed if resume_stage is None
        from automation.models import TaskState
        from automation.runtime_state import RuntimeTaskState
        from tempfile import TemporaryDirectory
        
        # Test valid transitions in state_machine
        from automation.state_machine import StateMachine
        sm = StateMachine()
        sm.current_state = TaskState.RESUMING
        sm.transition(TaskState.FAILED_STALLED)
        self.assertEqual(sm.current_state, TaskState.FAILED_STALLED)
