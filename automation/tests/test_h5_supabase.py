import unittest
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from automation.sql_safety import SQLSafetyClassifier
from automation.adapters.supabase_adapter import SupabaseAdapter, SupabaseAdapterError
from automation.models import SupabaseAccessMode, DatabaseChangeProposal, ApprovalAction, FutureEvents
from automation.approval_gate import ApprovalManager, ApprovalStatus

class TestH5_Supabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = self.temp_dir.name
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sql_safety_readonly(self):
        self.assertEqual(SQLSafetyClassifier.classify("SELECT * FROM users;"), "READ_ONLY")
        self.assertEqual(SQLSafetyClassifier.classify("EXPLAIN SELECT count(*) FROM orders;"), "READ_ONLY")
        # With comments
        self.assertEqual(SQLSafetyClassifier.classify("/* DROP TABLE users; */ SELECT * FROM users;"), "READ_ONLY")

    def test_sql_safety_write(self):
        self.assertEqual(SQLSafetyClassifier.classify("INSERT INTO users (id) VALUES (1);"), "WRITE")
        self.assertEqual(SQLSafetyClassifier.classify("UPDATE users SET name='test';"), "WRITE")
        self.assertEqual(SQLSafetyClassifier.classify("CREATE TABLE test (id int);"), "WRITE")

    def test_sql_safety_destructive(self):
        self.assertEqual(SQLSafetyClassifier.classify("DROP TABLE users;"), "DESTRUCTIVE")
        self.assertEqual(SQLSafetyClassifier.classify("TRUNCATE TABLE logs;"), "DESTRUCTIVE")
        
    def test_approval_id_separation(self):
        manager = ApprovalManager(self.test_dir)
        aid1 = manager.request_approval("task_1", ApprovalAction.DATABASE_WRITE.value, "DB change 1")
        aid2 = manager.request_approval("task_1", ApprovalAction.COMMIT.value, "Commit changes")
        
        self.assertNotEqual(aid1, aid2)
        apps = manager.get_task_approvals("task_1")
        self.assertEqual(len(apps), 2)
        
        # Test decide by approval_id
        manager.decide(aid1, True)
        self.assertEqual(manager.get_approval(aid1).status, ApprovalStatus.APPROVED)
        self.assertEqual(manager.get_approval(aid2).status, ApprovalStatus.PENDING)

    @patch('automation.adapters.supabase_adapter.PROJECT_ROOT', new_callable=lambda: tempfile.gettempdir())
    def test_supabase_adapter_project_scoping(self, mock_root):
        with patch.dict(os.environ, {"SUPABASE_PROJECT_ID": "mock-ref"}):
            adapter = SupabaseAdapter()
            self.assertEqual(adapter.project_ref, "mock-ref")
            self.assertTrue(adapter.is_linked)

    @patch('automation.adapters.supabase_adapter.PROJECT_ROOT', new_callable=lambda: tempfile.gettempdir())
    def test_supabase_adapter_readonly_default(self, mock_root):
        adapter = SupabaseAdapter()
        self.assertEqual(adapter.mode, SupabaseAccessMode.READ_ONLY)
        
    def test_db_change_proposal_hash(self):
        prop = DatabaseChangeProposal(
            proposal_id="p1",
            task_id="t1",
            project_ref="dummy",
            description="test",
            risk="WRITE",
            migration_sql_reference="file.sql",
            sql_hash="dummy_hash"
        )
        self.assertEqual(prop.sql_hash, "dummy_hash")

    @patch('automation.adapters.supabase_adapter.PROJECT_ROOT', new_callable=lambda: tempfile.gettempdir())
    @patch('subprocess.run')
    def test_db_inspection_event(self, mock_run, mock_root):
        with patch.dict(os.environ, {"SUPABASE_PROJECT_ID": "mock-ref"}):
            adapter = SupabaseAdapter()
            mock_run.return_value = MagicMock(returncode=0, stdout='{"rows": [{"name": "public.users"}]}', stderr="")
            evidence = adapter.inspect_db()
            self.assertEqual(evidence.project_ref, "mock-ref")
            self.assertIn("users", evidence.tables)

if __name__ == '__main__':
    unittest.main()
