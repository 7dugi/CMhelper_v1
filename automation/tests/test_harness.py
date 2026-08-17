import unittest
from automation.governance import GovernanceLoader
from automation.state_machine import StateMachine
from automation.models import TaskState, RiskLevel, SeniorPlan, ReviewResult, ValidationResult, ReviewStatus, ValidationStatus, AcceptanceCriterion
from automation.approval import RiskEvaluator
from automation.adapters.codex_adapter import CodexAdapter
from automation.adapters.antigravity_adapter import AntigravityAdapter
from automation.adapters.factory import ProviderFactory
from automation.orchestrator import PassGate, ReviewLoopGuard
from automation.config import PROJECT_ROOT

class TestHarness(unittest.TestCase):
    def test_governance_loader_core_docs(self):
        loader = GovernanceLoader()
        docs = loader.load_core_documents()
        self.assertIn(".agents/AGENTS.md", docs)
        self.assertTrue(docs[".agents/AGENTS.md"].exists)

    def test_project_root_escape_prevention(self):
        loader = GovernanceLoader()
        doc = loader.load_document("../../../windows/system32/cmd.exe")
        self.assertFalse(doc.exists)
        self.assertFalse(doc.loaded)

    def test_valid_state_transition(self):
        sm = StateMachine(TaskState.NEW)
        sm.transition(TaskState.PRE_FLIGHT)
        self.assertEqual(sm.current_state, TaskState.PRE_FLIGHT)

    def test_invalid_state_transition(self):
        sm = StateMachine(TaskState.NEW)
        with self.assertRaises(ValueError):
            sm.transition(TaskState.COMPLETED)

    def test_risk_red_requires_approval(self):
        evaluator = RiskEvaluator()
        risk = evaluator.classify("We will drop the production db table")
        self.assertEqual(risk, RiskLevel.RED)
        self.assertTrue(evaluator.requires_user_approval(risk))

    def test_codex_command_safe_flags(self):
        adapter = CodexAdapter()
        cmd = adapter.build_plan_command("test")
        args_str = " ".join(cmd.args)
        self.assertIn("windows.sandbox=\"unelevated\"", args_str)
        self.assertIn("--sandbox read-only", args_str)

    def test_codex_command_no_dangerous_bypass(self):
        adapter = CodexAdapter()
        cmd = adapter.build_plan_command("test")
        args_str = " ".join(cmd.args)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", args_str)

    def test_antigravity_command_workspace(self):
        adapter = AntigravityAdapter()
        cmd = adapter.build_command("test")
        args_str = " ".join(cmd.args)
        self.assertIn(f"--add-dir {PROJECT_ROOT}", args_str)

    def test_pass_gate_fails_on_validation(self):
        gate = PassGate()
        plan = SeniorPlan(summary="", scope=[], out_of_scope=[], acceptance_criteria=[], required_validations=["tests"], risk_level=RiskLevel.GREEN, designer_required=False, user_decision_required=False)
        review = ReviewResult(status=ReviewStatus.PASS, summary="", issues=[], evidence=[], next_instruction="", approval_question="", risk_level=RiskLevel.GREEN)
        val = ValidationResult(tests=ValidationStatus.FAIL)
        self.assertFalse(gate.evaluate(plan, review, val, False))

    def test_pass_gate_na_validation(self):
        gate = PassGate()
        plan = SeniorPlan(summary="", scope=[], out_of_scope=[], acceptance_criteria=[], required_validations=["tests"], risk_level=RiskLevel.GREEN, designer_required=False, user_decision_required=False)
        review = ReviewResult(status=ReviewStatus.PASS, summary="", issues=[], evidence=[], next_instruction="", approval_question="", risk_level=RiskLevel.GREEN)
        val = ValidationResult(tests=ValidationStatus.PASS, build=ValidationStatus.NOT_RUN)
        self.assertTrue(gate.evaluate(plan, review, val, False))

    def test_review_loop_guard_autonomous_limit(self):
        guard = ReviewLoopGuard()
        for _ in range(3):
            guard.record_review(["issue1"])
        self.assertTrue(guard.autonomous_limit_reached())

    def test_review_loop_guard_no_progress(self):
        guard = ReviewLoopGuard()
        guard.record_review(["syntax error in main"])
        guard.record_review(["syntax error in main"])
        self.assertTrue(guard.detect_no_progress())

    def test_review_loop_guard_oscillation(self):
        guard = ReviewLoopGuard()
        guard.record_implementation(["a.py"], "v1")
        guard.record_implementation(["b.py"], "v2")
        guard.record_implementation(["a.py"], "v1")
        self.assertTrue(guard.detect_oscillation())

    def test_provider_factory_antigravity(self):
        adapter = ProviderFactory.get_adapter("antigravity")
        self.assertIsInstance(adapter, AntigravityAdapter)

    def test_provider_factory_unsupported(self):
        with self.assertRaises(ValueError):
            ProviderFactory.get_adapter("unknown_provider")

if __name__ == "__main__":
    unittest.main()
