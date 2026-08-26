import unittest
from unittest.mock import patch, MagicMock
import json
import os
import tempfile
import sys
from automation.next_task_resolver import NextTaskResolver
from automation.models import NextTaskResolution, NextTaskCandidate
from automation.control import main as control_main
from automation.runtime_state import RuntimeStateManager
from automation.project_registry import ProjectRegistry

class TestNextTaskResolver(unittest.TestCase):
    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.resolver = NextTaskResolver(self.root_dir)
        self.bundle = {
            "project_id": "test_project",
            "phase_info": "",
            "documents": {
                "CURRENT_STATUS.md": "All good.",
                "ROADMAP.md": "Do next task."
            }
        }
        
        self.test_queue_dir = tempfile.TemporaryDirectory()
        self.test_registry_dir = tempfile.TemporaryDirectory()
        
        # Setup registry with test_project
        projects_dir = os.path.join(self.test_registry_dir.name, "projects")
        os.makedirs(projects_dir, exist_ok=True)
        
        project_root_dir = os.path.join(self.test_registry_dir.name, "test_project")
        os.makedirs(project_root_dir, exist_ok=True)
        
        self.registry = ProjectRegistry(self.test_registry_dir.name)
        with open(os.path.join(projects_dir, "test_project.yaml"), "w") as f:
            f.write("""
project_id: test_project
project_name: "Test Project"
project_root: "test_project"
repository: "test/test_project"
default_branch: "main"
development_branch: "feature/dev"
""")
        self.registry.load_all()
            
    def tearDown(self):
        self.test_queue_dir.cleanup()
        self.test_registry_dir.cleanup()

    @patch("automation.next_task_resolver.subprocess.Popen")
    def test_a_single_candidate_ready(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (json.dumps({
            "project_id": "test_project",
            "result": "READY",
            "reason": "Clear next task",
            "candidate": {
                "project_id": "test_project",
                "title": "Task 1",
                "description": "Do Task 1",
                "source_documents": ["ROADMAP.md"],
                "reason": "Top priority",
                "confidence": "HIGH",
                "risk_level": "GREEN",
                "requires_user_decision": False,
                "blocked_by": [],
                "acceptance_criteria": ["Done"]
            }
        }), "")
        mock_popen.return_value = mock_process
        
        res = self.resolver.resolve(self.bundle)
        self.assertEqual(res.result, "READY")
        self.assertEqual(res.candidate.confidence, "HIGH")

    @patch("automation.next_task_resolver.subprocess.Popen")
    def test_b_ambiguous(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (json.dumps({
            "project_id": "test_project",
            "result": "NEED_USER_DECISION",
            "reason": "Two equal candidates"
        }), "")
        mock_popen.return_value = mock_process
        
        res = self.resolver.resolve(self.bundle)
        self.assertEqual(res.result, "NEED_USER_DECISION")

    @patch("automation.next_task_resolver.subprocess.Popen")
    def test_c_architecture_decision(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (json.dumps({
            "project_id": "test_project",
            "result": "NEED_USER_DECISION",
            "reason": "Needs architecture decision"
        }), "")
        mock_popen.return_value = mock_process
        
        res = self.resolver.resolve(self.bundle)
        self.assertEqual(res.result, "NEED_USER_DECISION")

    @patch("automation.next_task_resolver.subprocess.Popen")
    def test_d_high_risk(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (json.dumps({
            "project_id": "test_project",
            "result": "NEED_USER_DECISION",
            "reason": "High risk destructive task"
        }), "")
        mock_popen.return_value = mock_process
        
        res = self.resolver.resolve(self.bundle)
        self.assertEqual(res.result, "NEED_USER_DECISION")

    @patch("automation.next_task_resolver.subprocess.Popen")
    def test_e_blocked_dependency(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (json.dumps({
            "project_id": "test_project",
            "result": "BLOCKED",
            "reason": "Dependency missing"
        }), "")
        mock_popen.return_value = mock_process
        
        res = self.resolver.resolve(self.bundle)
        self.assertEqual(res.result, "BLOCKED")

    @patch("automation.next_task_resolver.NextTaskResolver.resolve")
    @patch("automation.control.ProjectRegistry")
    @patch("automation.control.RuntimeStateManager")
    def test_f_duplicate_create(self, mock_rm_class, mock_registry_class, mock_resolve):
        mock_registry_class.return_value = self.registry
        
        mock_rm = MagicMock()
        mock_rm_class.return_value = mock_rm
        
        from automation.control import compute_hash
        req_hash = compute_hash("test_project" + "Duplicate task")
        mock_rm.get_queued_tasks.side_effect = [[], [MagicMock(request_id=req_hash)]]
        
        mock_resolve.return_value = NextTaskResolution(
            project_id="test_project",
            result="READY",
            reason="Go",
            candidate=NextTaskCandidate(
                project_id="test_project",
                title="Duplicate",
                description="Duplicate task",
                source_documents=["doc"],
                reason="Go",
                confidence="HIGH",
                risk_level="GREEN",
                requires_user_decision=False
            )
        )
        
        # Run first time
        with patch.object(sys, "argv", ["control.py", "next", "--project", "test_project", "--create"]):
            control_main()
            
        self.assertEqual(mock_rm.enqueue_task.call_count, 1)
        
        # Run second time, expecting exit due to deduplication
        with patch.object(sys, "argv", ["control.py", "next", "--project", "test_project", "--create"]):
            try:
                control_main()
            except SystemExit as e:
                self.assertEqual(e.code, 0)
                
        # Total enqueues should still be 1
        self.assertEqual(mock_rm.enqueue_task.call_count, 1)

    @patch("automation.next_task_resolver.NextTaskResolver.resolve")
    @patch("automation.control.ProjectRegistry")
    @patch("automation.control.RuntimeStateManager")
    def test_g_create_gate_conditions(self, mock_rm_class, mock_registry_class, mock_resolve):
        mock_registry_class.return_value = self.registry
        mock_rm = MagicMock()
        mock_rm_class.return_value = mock_rm
        mock_rm.get_queued_tasks.return_value = []
        
        # Test READY + MEDIUM -> No task created
        mock_resolve.return_value = NextTaskResolution(
            project_id="test_project", result="READY", reason="Medium confidence",
            candidate=NextTaskCandidate(
                project_id="test_project", title="Medium", description="Medium task",
                source_documents=["doc"], reason="Go", confidence="MEDIUM",
                risk_level="GREEN", requires_user_decision=False
            )
        )
        with patch.object(sys, "argv", ["control.py", "next", "--project", "test_project", "--create"]):
            control_main()
        self.assertEqual(mock_rm.enqueue_task.call_count, 0)

        # Test READY + LOW -> No task created
        mock_resolve.return_value.candidate.confidence = "LOW"
        with patch.object(sys, "argv", ["control.py", "next", "--project", "test_project", "--create"]):
            control_main()
        self.assertEqual(mock_rm.enqueue_task.call_count, 0)

        # Test NEED_USER_DECISION -> No task created
        mock_resolve.return_value = NextTaskResolution(project_id="test_project", result="NEED_USER_DECISION", reason="Decide")
        with patch.object(sys, "argv", ["control.py", "next", "--project", "test_project", "--create"]):
            control_main()
        self.assertEqual(mock_rm.enqueue_task.call_count, 0)

        # Test BLOCKED -> No task created
        mock_resolve.return_value = NextTaskResolution(project_id="test_project", result="BLOCKED", reason="Blocked")
        with patch.object(sys, "argv", ["control.py", "next", "--project", "test_project", "--create"]):
            control_main()
        self.assertEqual(mock_rm.enqueue_task.call_count, 0)

    @patch("automation.next_task_resolver.subprocess.Popen")
    def test_h_codex_failures(self, mock_popen):
        # 1. Malformed JSON
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("{ bad json", "")
        mock_popen.return_value = mock_process
        res = self.resolver.resolve(self.bundle)
        self.assertEqual(res.result, "BLOCKED")

        # 2. Schema Invalid (Missing result)
        mock_process.communicate.return_value = (json.dumps({"project_id": "test_project", "reason": "No result field"}), "")
        res = self.resolver.resolve(self.bundle)
        self.assertEqual(res.result, "BLOCKED")

        # 3. Non-zero exit (Timeout or error)
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("", "Error timeout")
        res = self.resolver.resolve(self.bundle)
        self.assertEqual(res.result, "BLOCKED")
        
    @patch("automation.next_task_resolver.NextTaskResolver.resolve")
    @patch("automation.control.ProjectRegistry")
    @patch("automation.control.RuntimeStateManager")
    def test_i_dedup_project_isolation(self, mock_rm_class, mock_registry_class, mock_resolve):
        # Setup registry with two projects
        projects_dir = os.path.join(self.test_registry_dir.name, "projects")
        with open(os.path.join(projects_dir, "project_a.yaml"), "w") as f:
            f.write('project_id: project_a\nproject_name: "A"\nproject_root: "test_project"\nrepository: "a/b"\ndefault_branch: "main"\ndevelopment_branch: "dev"')
        with open(os.path.join(projects_dir, "project_b.yaml"), "w") as f:
            f.write('project_id: project_b\nproject_name: "B"\nproject_root: "test_project"\nrepository: "a/c"\ndefault_branch: "main"\ndevelopment_branch: "dev"')
        
        self.registry.load_all()
        mock_registry_class.return_value = self.registry
        
        mock_rm = MagicMock()
        mock_rm_class.return_value = mock_rm
        
        # Test creation for Project A
        mock_resolve.return_value = NextTaskResolution(
            project_id="project_a", result="READY", reason="Go",
            candidate=NextTaskCandidate(project_id="project_a", title="T", description="Desc", source_documents=["d"], reason="R", confidence="HIGH", risk_level="GREEN", requires_user_decision=False)
        )
        mock_rm.get_queued_tasks.return_value = []
        with patch.object(sys, "argv", ["control.py", "next", "--project", "project_a", "--create"]):
            control_main()
        self.assertEqual(mock_rm.enqueue_task.call_count, 1)
        
        # Test creation for Project B with same description
        from automation.control import compute_hash
        hash_a = compute_hash("project_aDesc")
        mock_rm.get_queued_tasks.return_value = [MagicMock(request_id=hash_a)]
        
        mock_resolve.return_value.project_id = "project_b"
        mock_resolve.return_value.candidate.project_id = "project_b"
        
        with patch.object(sys, "argv", ["control.py", "next", "--project", "project_b", "--create"]):
            control_main()
        self.assertEqual(mock_rm.enqueue_task.call_count, 2)  # Should allow creation because hash uses project_id

if __name__ == "__main__":
    unittest.main()
