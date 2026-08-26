import unittest
from automation.discord_formatter import build_enhanced_approval_message
from automation.runtime_state import RuntimeTaskState

class TestDiscordFormatter(unittest.TestCase):
    def test_commit_notification(self):
        state = RuntimeTaskState(
            task_id="T1",
            project_id="P1",
            task_title="Test Task",
            task_description="Testing\nLine 2",
            allowed_mutation_paths=["foo.py", "bar.py"],
            last_successful_stage="FINAL_REVIEW",
            state="WAITING_FOR_USER_APPROVAL"
        )
        msg = build_enhanced_approval_message(state, "A1", "COMMIT", "Reason")
        self.assertIn("Project:\nP1", msg)
        self.assertIn("Task:\nTest Task", msg)
        self.assertIn("Task ID:\nT1", msg)
        self.assertIn("Approval:\nA1", msg)
        self.assertIn("Requested Action:\nCOMMIT", msg)
        self.assertIn("로컬 Git Commit으로 확정하기 위한 승인이 필요합니다", msg)
        self.assertIn("2 files changed\n- foo.py\n- bar.py", msg)
        self.assertIn("Tests: PASS", msg)
        self.assertIn("Risk:\nLOW", msg)
        self.assertIn("If approved:\n현재 승인 대상 파일만 Git Commit합니다.", msg)

    def test_push_notification(self):
        state = RuntimeTaskState(task_id="T2", state="WAITING_FOR_USER_APPROVAL")
        msg = build_enhanced_approval_message(state, "A2", "PUSH", "Reason")
        self.assertIn("로컬 Commit을 원격 GitHub Branch에", msg)
        self.assertIn("Risk:\nMEDIUM", msg)

    def test_database_write_notification(self):
        state = RuntimeTaskState(task_id="T3", state="WAITING_FOR_USER_APPROVAL")
        msg = build_enhanced_approval_message(state, "A3", "DATABASE_WRITE", "Reason")
        self.assertIn("데이터베이스 변경은 실제 데이터에 영향을 줄 수 있어", msg)
        self.assertIn("Risk:\nHIGH", msg)

    def test_production_deploy_notification(self):
        state = RuntimeTaskState(task_id="T6", state="WAITING_FOR_USER_APPROVAL")
        msg = build_enhanced_approval_message(state, "A6", "PRODUCTION_DEPLOY", "Reason")
        self.assertIn("변경사항을 Production 환경에 반영하기 위한", msg)
        self.assertIn("Risk:\nHIGH", msg)

    def test_long_changed_file_list(self):
        state = RuntimeTaskState(
            task_id="T4",
            state="WAITING_FOR_USER_APPROVAL",
            allowed_mutation_paths=[f"file{i}.py" for i in range(10)]
        )
        msg = build_enhanced_approval_message(state, "A4", "COMMIT", "Reason")
        self.assertIn("10 files changed", msg)
        self.assertIn("- file0.py", msg)
        self.assertIn("- file4.py", msg)
        self.assertNotIn("- file5.py", msg)
        self.assertIn("+ 5 more files", msg)

    def test_missing_evidence(self):
        state = RuntimeTaskState(task_id="T5", state="WAITING_FOR_USER_APPROVAL")
        msg = build_enhanced_approval_message(state, "A5", "COMMIT", "Reason")
        self.assertIn("Tests: UNKNOWN", msg)
        self.assertIn("Browser QA: UNKNOWN", msg)
        self.assertIn("Final Review: UNKNOWN", msg)

if __name__ == '__main__':
    unittest.main()
