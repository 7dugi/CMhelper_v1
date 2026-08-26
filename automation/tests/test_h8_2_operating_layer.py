import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock
import sys

from automation.project_config import ProjectConfig, OperatingLayerConfig
from automation.operating_layer import ProjectOperatingLayer, FreshnessState, OperatingMode
from automation.models import NextTaskResolution, NextTaskCandidate
from automation.control import main as control_main
from automation.project_registry import ProjectRegistry

class TestOperatingLayer(unittest.TestCase):
    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.test_registry_dir = tempfile.TemporaryDirectory()
        projects_dir = os.path.join(self.test_registry_dir.name, "projects")
        os.makedirs(projects_dir, exist_ok=True)
        
        self.project_root = os.path.join(self.test_registry_dir.name, "cmhelper")
        os.makedirs(self.project_root, exist_ok=True)
        
        self.registry = ProjectRegistry(self.test_registry_dir.name)
        with open(os.path.join(projects_dir, "cmhelper.yaml"), "w") as f:
            f.write("""
project_id: cmhelper
project_name: "CMhelper B2B SaaS"
project_root: "cmhelper"
repository: "test/repo"
default_branch: "main"
development_branch: "feature/dev"
operating_layer:
  freshness_sources:
    - "docs/CURRENT_STATUS.md"
""")
        self.registry.load_all()
        self.project = self.registry.get_project("cmhelper")
        self.op_layer = ProjectOperatingLayer(self.test_registry_dir.name)
        
    def tearDown(self):
        self.test_registry_dir.cleanup()

    @patch("automation.operating_layer.subprocess.check_output")
    def test_a_bootstrap(self, mock_subprocess):
        mock_subprocess.side_effect = ["feature/dev", "123456", ""]
        output = self.op_layer.bootstrap(self.project)
        self.assertIn("=== BOOTSTRAP: CMhelper B2B SaaS ===", output)
        self.assertIn("Git Branch: feature/dev", output)
        self.assertIn("Freshness: FRESH", output)
        
    @patch("automation.operating_layer.subprocess.check_output")
    def test_f_conflict_freshness(self, mock_subprocess):
        mock_subprocess.side_effect = ["feature/dev", "123456", "M docs/CURRENT_STATUS.md"]
        freshness = self.op_layer.check_freshness(self.project)
        self.assertEqual(freshness, FreshnessState.CONFLICT)
        
    @patch("automation.operating_layer.subprocess.check_output")
    @patch("automation.operating_layer.Path.exists")
    @patch("automation.operating_layer.Path.iterdir")
    def test_e_stale_freshness(self, mock_iterdir, mock_exists, mock_check_output):
        # Setup so that audit log is newer than the doc
        mock_exists.return_value = True
        
        # mock iterdir to return one fake task directory
        fake_task_dir = MagicMock()
        fake_task_dir.is_dir.return_value = True
        fake_index = MagicMock()
        fake_index.exists.return_value = True
        fake_task_dir.__truediv__.return_value = fake_index
        mock_iterdir.return_value = [fake_task_dir]
        
        task_stat = MagicMock()
        task_stat.st_mtime = 1000
        fake_task_dir.stat.return_value = task_stat
        
        # Git commit time is 500 (STALE)
        mock_check_output.side_effect = ["feature/dev", "123456", "", "500"]
        
        freshness = self.op_layer.check_freshness(self.project)
        self.assertEqual(freshness, FreshnessState.STALE)
        
    @patch("automation.next_task_resolver.NextTaskResolver.resolve")
    @patch("automation.control.ProjectRegistry")
    @patch("automation.control.RuntimeStateManager")
    @patch("automation.operating_layer.ProjectOperatingLayer.check_freshness")
    def test_d_execute_gate_fresh(self, mock_freshness, mock_rm_class, mock_registry_class, mock_resolve):
        mock_registry_class.return_value = self.registry
        mock_rm = MagicMock()
        mock_rm_class.return_value = mock_rm
        mock_rm.get_queued_tasks.return_value = []
        
        mock_freshness.return_value = FreshnessState.FRESH
        mock_resolve.return_value = NextTaskResolution(
            project_id="cmhelper", result="READY", reason="Go",
            candidate=NextTaskCandidate(project_id="cmhelper", title="T", description="D", source_documents=["d"], reason="r", confidence="HIGH", risk_level="GREEN", requires_user_decision=False)
        )
        
        with patch.object(sys, "argv", ["control.py", "next", "--project", "cmhelper", "--create"]):
            control_main()
            
        self.assertEqual(mock_rm.enqueue_task.call_count, 1)

    @patch("automation.next_task_resolver.NextTaskResolver.resolve")
    @patch("automation.control.ProjectRegistry")
    @patch("automation.control.RuntimeStateManager")
    @patch("automation.operating_layer.ProjectOperatingLayer.check_freshness")
    def test_e_execute_gate_stale(self, mock_freshness, mock_rm_class, mock_registry_class, mock_resolve):
        mock_registry_class.return_value = self.registry
        mock_rm = MagicMock()
        mock_rm_class.return_value = mock_rm
        mock_rm.get_queued_tasks.return_value = []
        
        mock_freshness.return_value = FreshnessState.STALE
        mock_resolve.return_value = NextTaskResolution(
            project_id="cmhelper", result="READY", reason="Go",
            candidate=NextTaskCandidate(project_id="cmhelper", title="T", description="D", source_documents=["d"], reason="r", confidence="HIGH", risk_level="GREEN", requires_user_decision=False)
        )
        
        with patch.object(sys, "argv", ["control.py", "next", "--project", "cmhelper", "--create"]):
            try:
                control_main()
            except SystemExit as e:
                self.assertEqual(e.code, 0)
            
        self.assertEqual(mock_rm.enqueue_task.call_count, 0)

if __name__ == "__main__":
    unittest.main()
