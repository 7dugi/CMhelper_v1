import unittest
from unittest.mock import patch, MagicMock
from automation.permission_manager import PermissionManager
from automation.evidence_executor import EvidenceExecutor
from automation.models import SeniorPlan, ValidationResult, ReviewResult, ReviewStatus, RiskLevel

class TestH3(unittest.TestCase):

    def setUp(self):
        self.pm = PermissionManager()
        self.executor = EvidenceExecutor()

    def test_allowed_mutation_paths_validation(self):
        plan = SeniorPlan(
            summary="test",
            scope=[],
            out_of_scope=[],
            acceptance_criteria=[],
            required_validations=[],
            risk_level=RiskLevel.GREEN,
            designer_required=False,
            user_decision_required=False,
            allowed_mutation_paths=["automation/README.md"]
        )
        self.assertEqual(plan.allowed_mutation_paths, ["automation/README.md"])

    @patch('automation.permission_manager.Path.exists')
    @patch('automation.permission_manager.shutil.copy2')
    @patch('automation.permission_manager.open')
    @patch('automation.permission_manager.json.load')
    def test_scoped_write_permission_generation(self, mock_json_load, mock_open, mock_copy, mock_exists):
        mock_exists.return_value = True
        mock_json_load.return_value = {"permissions": {"allow": []}}
        
        # Test success
        with patch('automation.permission_manager.json.dump') as mock_dump:
            res = self.pm.apply_scoped_permissions(["automation/README.md"])
            self.assertTrue(res)
            mock_dump.assert_called_once()
            args, _ = mock_dump.call_args
            self.assertIn("write_file(automation/README.md)", args[0]['permissions']['allow'])

    @patch('automation.permission_manager.PermissionManager.restore_permissions')
    @patch('automation.permission_manager.PermissionManager._ensure_paths')
    @patch('automation.permission_manager.shutil.copy2')
    @patch('automation.permission_manager.open')
    @patch('automation.permission_manager.json.load')
    def test_write_file_wildcard_rejection(self, mock_load, mock_open, mock_copy, mock_ensure, mock_restore):
        mock_load.return_value = {"permissions": {"allow": []}}
        # The permission manager should reject wildcards
        res = self.pm.apply_scoped_permissions(["automation/*"])
        self.assertFalse(res)
        mock_restore.assert_called_once()

    @patch('automation.evidence_executor.EvidenceExecutor._run_git')
    def test_baseline_aware_mutation_detection(self, mock_run_git):
        # Before: file A and B modified
        mock_run_git.return_value = " M fileA.py\n?? fileB.py"
        self.executor.capture_baseline()
        
        # After: file A, B, and C modified
        mock_run_git.return_value = " M fileA.py\n?? fileB.py\n M fileC.py"
        delta = self.executor.get_actual_new_mutation()
        
        self.assertEqual(set(delta), {"fileC.py"})

    def test_review_revise_routing(self):
        res = ReviewResult(
            status=ReviewStatus.REVISE,
            summary="test",
            issues=["Needs fix"]
        )
        self.assertEqual(res.status, ReviewStatus.REVISE)

if __name__ == '__main__':
    unittest.main()
