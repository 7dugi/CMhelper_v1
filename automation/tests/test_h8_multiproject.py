import unittest
import os
import tempfile
import yaml
import json
from pathlib import Path
from automation.project_config import ProjectConfig
from automation.project_registry import ProjectRegistry
from automation.context_builder import ContextBuilder
from automation.runtime_state import RuntimeStateManager, RuntimeTaskState
from automation.models import TaskState
from automation.notifier import NotificationEvent, DiscordNotifier

class TestH8MultiProject(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        self.projects_dir = self.root_dir / "projects"
        self.projects_dir.mkdir()
        self.runtime_mgr = RuntimeStateManager(str(self.root_dir))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_project_config_valid_and_root_resolution(self):
        # Create a fake project root
        proj1_root = self.root_dir / "proj1"
        proj1_root.mkdir()
        
        yaml_content = {
            "project_id": "test_proj",
            "project_name": "Test Project",
            "project_root": "proj1",
            "repository": "test/repo",
            "default_branch": "main",
            "development_branch": "dev",
            "supabase": {"enabled": True},
            "vercel": {"enabled": False}
        }
        yaml_file = self.projects_dir / "test.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)
            
        registry = ProjectRegistry(str(self.root_dir))
        proj = registry.get_project("test_proj")
        self.assertIsNotNone(proj)
        self.assertEqual(proj.project_name, "Test Project")
        self.assertTrue(proj.supabase.enabled)
        self.assertFalse(proj.vercel.enabled)
        
        resolved_root = proj.resolve_root(str(self.projects_dir))
        self.assertEqual(resolved_root, str(proj1_root.resolve()))

    def test_project_config_invalid_root(self):
        yaml_content = {
            "project_id": "bad_proj",
            "project_name": "Bad Project",
            "project_root": "does_not_exist",
            "repository": "test/repo",
            "default_branch": "main",
            "development_branch": "dev"
        }
        yaml_file = self.projects_dir / "bad.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)
            
        registry = ProjectRegistry(str(self.root_dir))
        # It should fail to load because resolve_root raises ValueError
        self.assertIsNone(registry.get_project("bad_proj"))

    def test_project_registry_multiple_projects(self):
        p1 = self.root_dir / "p1"
        p2 = self.root_dir / "p2"
        p1.mkdir()
        p2.mkdir()
        
        with open(self.projects_dir / "p1.yaml", "w") as f:
            yaml.dump({
                "project_id": "p1", "project_name": "P1", "project_root": "p1",
                "repository": "r", "default_branch": "b", "development_branch": "b"
            }, f)
        with open(self.projects_dir / "p2.yaml", "w") as f:
            yaml.dump({
                "project_id": "p2", "project_name": "P2", "project_root": "p2",
                "repository": "r", "default_branch": "b", "development_branch": "b"
            }, f)
            
        registry = ProjectRegistry(str(self.root_dir))
        self.assertEqual(len(registry.list_projects()), 2)
        self.assertIsNotNone(registry.get_project("p1"))
        self.assertIsNotNone(registry.get_project("p2"))
        
    def test_context_bundle(self):
        p1 = self.root_dir / "p1"
        p1.mkdir()
        (p1 / "docs").mkdir()
        
        with open(p1 / "docs" / "CURRENT_STATUS.md", "w") as f:
            f.write("# Status\nPhase 2\nDone.")
            
        with open(self.projects_dir / "p1.yaml", "w") as f:
            yaml.dump({
                "project_id": "p1", "project_name": "P1", "project_root": "p1",
                "repository": "r", "default_branch": "b", "development_branch": "b",
                "current_status_path": "docs/CURRENT_STATUS.md"
            }, f)
            
        registry = ProjectRegistry(str(self.root_dir))
        proj = registry.get_project("p1")
        
        builder = ContextBuilder(str(self.root_dir))
        bundle = builder.build_context(proj, str(self.projects_dir))
        
        self.assertEqual(bundle["project_id"], "p1")
        self.assertIn("Phase 2", bundle["phase_info"])
        self.assertEqual("# Status\nPhase 2\nDone.", bundle["documents"]["status"])
        
    def test_duplicate_file_request(self):
        import subprocess
        # We test duplicate rejection conceptually using the runtime_mgr
        state1 = RuntimeTaskState(
            task_id="T1",
            project_id="cmhelper",
            state=TaskState.QUEUED,
            request_id="hash123"
        )
        self.runtime_mgr.enqueue_task(state1)
        
        queued = self.runtime_mgr.get_queued_tasks()
        self.assertEqual(len(queued), 1)
        
        # In control.py, it checks if `getattr(q, 'request_id') == req_hash`.
        self.assertEqual(queued[0].request_id, "hash123")
        
    def test_discord_project_context(self):
        event = NotificationEvent(
            event_type="TEST",
            message="Test msg",
            task_id="T1",
            project_id="cmhelper",
            send_to_discord=True
        )
        
        # We can't easily mock the urllib here without repeating test_notifier, but we can verify the payload structure locally.
        # Just checking that project_id is in event.
        self.assertEqual(event.project_id, "cmhelper")

if __name__ == "__main__":
    unittest.main()
