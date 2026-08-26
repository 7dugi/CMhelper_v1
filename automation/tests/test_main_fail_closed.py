import unittest
import json
import tempfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from automation.config import PROJECT_ROOT
from automation.main import (
    build_implementation_prompt,
    build_planning_prompt,
    build_senior_review_prompt,
    commit_gate,
    implementation_gate,
    load_pre_review_evidence,
    load_pre_validation_evidence,
    approved_takeover_changes,
    notify_terminal_block,
    save_validation_execution_evidence,
    is_cmhelper_pc_agent_auth_task,
    validation_is_required,
    requires_preview_invalid_credential_verification,
    has_preview_invalid_credential_evidence,
    has_manual_preview_acceptance_evidence,
    collect_verified_source_diff,
    execute_approved_push,
    parse_implementation_result,
    planner_requires_user_decision,
    subprocess_gate,
    to_dict,
)
from automation.models import (
    ImplementationResult,
    ReviewResult,
    ReviewStatus,
    RiskLevel,
    SeniorPlan,
    TaskState,
    ValidationResult,
    ValidationStatus,
    BrowserQAResult,
)
from automation.notifier import NotificationSeverity


def plan(required_validations=None, user_decision_required=False):
    return SeniorPlan(
        summary="synthetic mutation task",
        scope=[],
        out_of_scope=[],
        acceptance_criteria=[],
        required_validations=required_validations or ["tests"],
        risk_level=RiskLevel.GREEN,
        designer_required=False,
        user_decision_required=user_decision_required,
        allowed_mutation_paths=["CMhelper_web/backend/app/main.py"],
    )


def implementation(**overrides):
    data = {
        "summary": "implemented requested change",
        "changed_files": ["CMhelper_web/backend/app/main.py"],
        "user_decision_required": False,
    }
    data.update(overrides)
    return ImplementationResult(**data)


class TestMainFailClosed(unittest.TestCase):
    def test_optional_preview_and_ui_are_not_treated_as_required(self):
        approved_plan = plan(["tests", "build"])
        self.assertFalse(validation_is_required(approved_plan, "preview"))
        self.assertFalse(validation_is_required(approved_plan, "ui"))
        self.assertTrue(validation_is_required(approved_plan, "tests"))

    def test_preview_and_ui_remain_required_when_explicitly_planned(self):
        approved_plan = plan(["tests", "preview", "ui"])
        self.assertTrue(validation_is_required(approved_plan, "preview"))
        self.assertTrue(validation_is_required(approved_plan, "ui"))

    def test_push_requires_matching_approved_gate_and_committed_sha(self):
        state = unittest.mock.Mock(
            task_id="push-task", blocking_approval_id="push-approval", commit_sha="abc123"
        )
        approval = unittest.mock.Mock(
            task_id="push-task", action="PUSH", status=unittest.mock.Mock(value="APPROVED")
        )
        # Use the concrete enum so a truthy mock cannot accidentally bypass the gate.
        from automation.approval_gate import ApprovalStatus
        approval.status = ApprovalStatus.APPROVED
        approvals = unittest.mock.Mock()
        approvals.get_approval.return_value = approval
        git = unittest.mock.Mock()
        git.get_current_branch.return_value = "feature/dev-harness-v1"
        evidence = execute_approved_push(approvals, state, git)
        git.push.assert_called_once_with()
        self.assertEqual(evidence["status"], "PUSHED")

        approval.status = ApprovalStatus.PENDING
        with self.assertRaises(RuntimeError):
            execute_approved_push(approvals, state, git)

    def test_preview_invalid_credential_evidence_requires_complete_401_flow(self):
        description = "Preview-only runtime verification with a fake invalid credential only."
        self.assertTrue(requires_preview_invalid_credential_verification(description))
        scenario = {"steps": [
            {"action": "fill", "selector_or_target": "input[type='email']"},
            {"action": "fill", "selector_or_target": "input[type='password']"},
            {"action": "click", "selector_or_target": "button[type='submit']"},
            {"action": "assert_network_status", "selector_or_target": "POST /api/auth/login", "expected": "401"},
            {"action": "assert_text", "selector_or_target": "body", "expected": "Invalid credentials"},
        ]}
        result = {"status": "PASS", "steps": [
            {"action": "fill", "status": "PASS"},
            {"action": "fill", "status": "PASS"},
            {"action": "click", "status": "PASS"},
            {"action": "assert_network_status", "status": "PASS", "actual": "POST /api/auth/login -> 401"},
            {"action": "assert_text", "status": "PASS", "actual": "Invalid credentials"},
        ]}
        self.assertTrue(has_preview_invalid_credential_evidence(scenario, result))
        result["steps"][3]["actual"] = "POST /api/auth/login -> 200"
        self.assertFalse(has_preview_invalid_credential_evidence(scenario, result))

    def test_browser_qa_evidence_is_json_serializable(self):
        evidence = to_dict(BrowserQAResult(
            scenario_id="qa-evidence",
            status="PASS",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        ))
        self.assertIsInstance(evidence["started_at"], str)
        self.assertEqual(json.loads(json.dumps(evidence))["status"], "PASS")

    def test_validation_resume_restores_persisted_implementation_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = unittest.mock.Mock(report_dir=directory)
            Path(directory, "senior_plan.json").write_text(json.dumps(plan().model_dump(mode="json")), encoding="utf-8")
            Path(directory, "implementation_result_i1.json").write_text(json.dumps(implementation().model_dump(mode="json")), encoding="utf-8")
            Path(directory, "implementation_evidence_i1.json").write_text(json.dumps({
                "verified_changed_files": ["CMhelper_web/backend/app/main.py"]
            }), encoding="utf-8")
            restored_plan, restored_implementation, actual_changes = load_pre_validation_evidence(audit, 1)
        self.assertEqual(restored_plan.allowed_mutation_paths, ["CMhelper_web/backend/app/main.py"])
        self.assertEqual(restored_implementation.changed_files, actual_changes)

    def test_implementation_prompt_uses_approved_plan_not_raw_task_history(self):
        approved_plan = plan()
        approved_plan.summary = "Implement the focused change"
        approved_plan.scope = ["Modify the approved frontend flow"]
        approved_plan.out_of_scope = ["Do not modify backend"]
        prompt = build_implementation_prompt(approved_plan, approved_plan.allowed_mutation_paths)
        self.assertIn("Implement the focused change", prompt)
        self.assertIn("Modify the approved frontend flow", prompt)
        self.assertIn("Do not modify backend", prompt)
        self.assertNotIn("Task:", prompt)

    def test_implementation_revision_prompt_carries_final_review_issues(self):
        prompt = build_implementation_prompt(
            plan(),
            ["CMhelper_web/backend/app/main.py"],
            ["Restore the existing editable Contract field."],
        )
        self.assertIn("Restore the existing editable Contract field.", prompt)
        self.assertIn('"revision_issues"', prompt)

    def test_validation_execution_evidence_records_exit_codes_and_bounded_output(self):
        audit = unittest.mock.Mock()
        save_validation_execution_evidence(
            audit,
            1,
            "cmhelper_phase3d_backend",
            {"exit_code": 1, "commands": [["python", "-m", "pytest"]], "stdout": "x" * 5000, "stderr": "failure"},
            {"exit_code": 0, "stdout": "compiled", "stderr": ""},
        )
        filename, payload = audit.save_json.call_args.args
        self.assertEqual(filename, "validation_execution_i1.json")
        self.assertEqual(payload["test_profile"], "cmhelper_phase3d_backend")
        self.assertEqual(payload["tests"]["exit_code"], 1)
        self.assertEqual(len(payload["tests"]["stdout_tail"]), 4000)
        self.assertEqual(payload["build"]["exit_code"], 0)

    def test_implementer_prompt_is_mutation_only_and_defers_validation_to_harness(self):
        approved_plan = plan()
        approved_plan.summary = "Update the approved backend migration."
        prompt = build_implementation_prompt(
            approved_plan,
            approved_plan.allowed_mutation_paths,
        )
        self.assertIn("Modify only files in Allowed Mutation Paths", prompt)
        self.assertIn("return exactly one valid JSON ImplementationResult object", prompt)
        self.assertIn("only files newly created or whose content was changed during this Antigravity invocation", prompt)
        self.assertIn("already dirty before this invocation unless you changed their content", prompt)
        self.assertIn("Forbidden: pytest, unittest, compileall, npm test, build, shell, PowerShell, bash", prompt)
        self.assertIn("Harness VALIDATING stage exclusively runs tests and verification", prompt)

    def test_implementation_result_is_extracted_from_markdown_wrapped_output(self):
        payload = json.dumps(implementation().model_dump())
        result = parse_implementation_result(f"Implementation complete.\n```json\n{payload}\n```\nDetails follow.")
        self.assertEqual(result.changed_files, ["CMhelper_web/backend/app/main.py"])

    def test_implementation_result_rejects_non_schema_json(self):
        with self.assertRaises(ValueError):
            parse_implementation_result('{"status": "COMPLETED", "modified_files": []}')

    def test_implementation_result_rejects_changed_files_only_payload(self):
        with self.assertRaises(ValueError):
            parse_implementation_result('{"changed_files": ["CMhelper_web/backend/app/main.py"]}')

    def test_implementation_result_extracts_agy_structured_output_wrapper(self):
        raw = json.dumps({
            "status": "SUCCESS",
            "structured_output": {
                "summary": "schema probe",
                "changed_files": ["CMhelper_web/backend/app/main.py"],
            },
        })
        result = parse_implementation_result(raw)
        self.assertEqual(result.summary, "schema probe")
        self.assertEqual(result.changed_files, ["CMhelper_web/backend/app/main.py"])

    def test_read_only_planner_prompt_does_not_require_user_decision_for_clear_work(self):
        prompt = build_planning_prompt("Add the approved migration test.", {"documents": {"docs/ROADMAP.md": "evidence"}})
        self.assertIn("intentionally read-only", prompt)
        self.assertIn("must never be used to infer", prompt)
        self.assertIn("PermissionManager scoped-write gate", prompt)
        self.assertIn("Harness-loaded repository context", prompt)
        self.assertIn("docs/ROADMAP.md", prompt)
        self.assertFalse(planner_requires_user_decision(plan()))

    def test_pre_preview_review_does_not_revise_for_later_required_evidence(self):
        prompt = build_senior_review_prompt(
            plan(["tests", "build", "preview", "ui"]), implementation(),
            ["CMhelper_web/backend/app/main.py"], ["CMhelper_web/backend/app/main.py"],
            ValidationResult(tests=ValidationStatus.PASS, build=ValidationStatus.PASS),
            "tests", {"exit_code": 0}, "build", {"exit_code": 0}, {"exit_code": 0},
            {"diff_check": {"exit_code": 0}, "status": {"exit_code": 0}},
        )
        self.assertIn("do not return REVISE merely because they are NOT_RUN", prompt)
        self.assertIn("Final Review must still require every validation category", prompt)
        self.assertIn("Task objective:", prompt)
        self.assertIn("necessary, behavior-preserving syntax repair", prompt)

    def test_review_resume_restores_persisted_pre_review_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit = unittest.mock.Mock(report_dir=temp_dir)
            Path(temp_dir, "senior_plan.json").write_text(json.dumps(plan(["tests", "build"]).model_dump(mode="json")), encoding="utf-8")
            Path(temp_dir, "implementation_result_i1.json").write_text(json.dumps(implementation().model_dump(mode="json")), encoding="utf-8")
            Path(temp_dir, "implementation_evidence_i1.json").write_text(json.dumps({"verified_changed_files": ["CMhelper_web/backend/app/main.py"]}), encoding="utf-8")
            Path(temp_dir, "validation_result_i1.json").write_text(json.dumps(ValidationResult(tests=ValidationStatus.PASS, build=ValidationStatus.PASS).model_dump(mode="json")), encoding="utf-8")
            Path(temp_dir, "validation_execution_i1.json").write_text(json.dumps({"test_profile": "tests", "tests": {"exit_code": 0}, "build": {"exit_code": 0}, "git_hygiene": {"diff_check_exit_code": 0, "status_exit_code": 0}}), encoding="utf-8")
            Path(temp_dir, "harness_compileall_i1.json").write_text(json.dumps({"exit_code": 0}), encoding="utf-8")
            Path(temp_dir, "review_result_i1.json").write_text(json.dumps(
                ReviewResult(status=ReviewStatus.PASS, summary="pass", evidence=["review evidence"]).model_dump(mode="json")
            ), encoding="utf-8")
            restored = load_pre_review_evidence(audit, 2)
        self.assertEqual(restored[0].allowed_mutation_paths, ["CMhelper_web/backend/app/main.py"])
        self.assertEqual(restored[2], ["CMhelper_web/backend/app/main.py"])
        self.assertEqual(restored[4], "tests")
        self.assertEqual(restored[8]["exit_code"], 0)
        self.assertEqual(restored[10].status, ReviewStatus.PASS)

    def test_genuine_planner_user_decision_is_preserved(self):
        self.assertTrue(planner_requires_user_decision(plan(user_decision_required=True)))

    def test_implementer_did_nothing_is_stalled(self):
        state, reason = implementation_gate(
            implementation(changed_files=[]),
            [],
            plan().allowed_mutation_paths,
        )
        self.assertEqual(state, TaskState.FAILED_STALLED)
        self.assertIn("no reported", reason)

    def test_takeover_requires_every_allowed_path_to_be_preexisting_dirty(self):
        allowed = plan().allowed_mutation_paths
        self.assertEqual(approved_takeover_changes({allowed[0]: (" M", "hash")}, allowed), allowed)
        with self.assertRaises(ValueError):
            approved_takeover_changes({}, allowed)

    def test_read_only_workspace_requires_user_decision(self):
        state, reason = implementation_gate(
            implementation(summary="Workspace is read-only and approvals disabled", changed_files=[]),
            [],
            plan().allowed_mutation_paths,
        )
        self.assertEqual(state, TaskState.NEED_USER_DECISION)
        self.assertIn("write permission", reason)

    def test_review_process_failure_is_stalled(self):
        state, reason = subprocess_gate(1, "Review")
        self.assertEqual(state, TaskState.FAILED_STALLED)
        self.assertEqual(reason, "Review command failed with exit code 1")

    def test_required_validation_not_run_blocks_commit(self):
        validation = ValidationResult(tests=ValidationStatus.NOT_RUN)
        review = ReviewResult(status=ReviewStatus.PASS, summary="pass", evidence=["synthetic evidence"])
        self.assertFalse(
            commit_gate(
                plan(["tests"]),
                implementation(),
                ["CMhelper_web/backend/app/main.py"],
                validation,
                review,
            )
        )

    def test_pass_requires_verified_changes_review_evidence_and_validation(self):
        validation = ValidationResult(tests=ValidationStatus.PASS)
        review = ReviewResult(status=ReviewStatus.PASS, summary="pass", evidence=["synthetic evidence"])
        self.assertTrue(
            commit_gate(
                plan(["tests"]),
                implementation(),
                ["CMhelper_web/backend/app/main.py"],
                validation,
                review,
            )
        )

    def test_absolute_and_relative_paths_are_canonicalized_without_scope_bypass(self):
        backend_file = "CMhelper_web/backend/app/main.py"
        absolute_backend_file = str(Path(PROJECT_ROOT) / backend_file)
        state, reason = implementation_gate(
            implementation(changed_files=[absolute_backend_file]),
            [backend_file],
            [backend_file],
        )
        self.assertIsNone(state)
        self.assertIsNone(reason)

        state, _ = implementation_gate(
            implementation(changed_files=[str(Path(PROJECT_ROOT).parent / "outside.py")]),
            [backend_file],
            [backend_file],
        )
        self.assertEqual(state, TaskState.FAILED_STALLED)

    def test_scoped_write_gate_allows_only_canonical_allowed_path(self):
        backend_file = "CMhelper_web/backend/app/main.py"
        self.assertEqual(
            implementation_gate(implementation(), [backend_file], [backend_file]),
            (None, None),
        )
        state, _ = implementation_gate(
            implementation(changed_files=["automation/main.py"]),
            ["automation/main.py"],
            [backend_file],
        )
        self.assertEqual(state, TaskState.FAILED_STALLED)

    def test_manual_preview_acceptance_requires_all_non_mutating_checks(self):
        checks = {
            "won_quote_0_blank_form": "PASS",
            "won_quote_1_prefill_editable": "PASS",
            "won_quote_multiple_select_prefill": "PASS",
            "non_won_conversion_blocked": "PASS",
            "cancel_close_back_no_creation": "PASS",
            "manual_contract_add_regression": "PASS",
        }
        with tempfile.TemporaryDirectory() as directory:
            evidence_path = Path(directory) / "manual_preview_acceptance.json"
            evidence_path.write_text(json.dumps({
                "status": "PASS",
                "preview_url": "https://preview.example.test",
                "save_action": "NOT_CLICKED",
                "checks": checks,
            }), encoding="utf-8")
            passed, evidence = has_manual_preview_acceptance_evidence(directory)
            self.assertTrue(passed)
            self.assertEqual(evidence["checks"], checks)

            checks["manual_contract_add_regression"] = "FAIL"
            evidence_path.write_text(json.dumps({
                "status": "PASS",
                "preview_url": "https://preview.example.test",
                "save_action": "NOT_CLICKED",
                "checks": checks,
            }), encoding="utf-8")
            passed, _ = has_manual_preview_acceptance_evidence(directory)
            self.assertFalse(passed)

    @patch("automation.main.subprocess.run")
    def test_final_review_source_evidence_is_limited_to_verified_paths(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="diff --git a/allowed.js b/allowed.js\n+", stderr=""
        )
        diff = collect_verified_source_diff(["CMhelper_web/frontend/src/App.jsx"])
        self.assertIn("allowed.js", diff)
        command = mock_run.call_args.args[0]
        self.assertEqual(command[:4], ["git", "diff", "--unified=3", "--"])
        self.assertEqual(command[4:], ["CMhelper_web/frontend/src/App.jsx"])

    def test_task_wide_report_with_single_invocation_delta_is_denied(self):
        allowed = [
            "CMhelper_web/backend/app/main.py",
            "CMhelper_web/backend/tests/test_migrations.py",
            "CMhelper_web/backend/tests/test_opportunity_conversion.py",
            "CMhelper_web/backend/tests/test_contracts.py",
            "CMhelper_web/backend/tests/test_auth.py",
        ]
        state, _ = implementation_gate(
            implementation(changed_files=allowed),
            ["CMhelper_web/backend/tests/test_auth.py"],
            allowed,
        )
        self.assertEqual(state, TaskState.FAILED_STALLED)

    def test_out_of_scope_invocation_delta_is_denied(self):
        state, _ = implementation_gate(
            implementation(changed_files=["automation/main.py"]),
            ["automation/main.py"],
            plan().allowed_mutation_paths,
        )
        self.assertEqual(state, TaskState.FAILED_STALLED)

    @patch("automation.main.dispatch_notification")
    def test_user_decision_notification_requests_discord_delivery(self, mock_dispatch):
        notify_terminal_block(
            "synthetic-task",
            "cmhelper",
            "IMPLEMENTATION_BLOCKED",
            "Implementer requires write permission",
            NotificationSeverity.ACTION_REQUIRED,
        )
        event = mock_dispatch.call_args.args[0]
        self.assertEqual(event.event_type, "IMPLEMENTATION_BLOCKED")
        self.assertTrue(event.send_to_discord)
        self.assertEqual(event.severity, NotificationSeverity.ACTION_REQUIRED)

    def test_is_cmhelper_pc_agent_auth_task_routing(self):
        # 1. Matches agent mutation paths
        self.assertTrue(is_cmhelper_pc_agent_auth_task(
            task_description="Implement auth for agent",
            allowed_mutation_paths=["CMhelper_agent/agent.py", "CMhelper_agent/api_client.py"],
            summary="Agent auth work",
        ))
        # 2. Matches agent keywords in description/summary
        self.assertTrue(is_cmhelper_pc_agent_auth_task(
            task_description="Implement process-memory-only JWT authentication for the Windows PC Agent",
            allowed_mutation_paths=[],
            summary="PC Agent authentication",
        ))
        # 3. Non-agent tasks return False (Phase 3D backend/frontend)
        self.assertFalse(is_cmhelper_pc_agent_auth_task(
            task_description="Won quote conversion contract creation workflow",
            allowed_mutation_paths=["CMhelper_web/backend/app/main.py", "CMhelper_web/frontend/src/App.jsx"],
            summary="Phase 3D contract conversion",
        ))

    def test_validation_execution_evidence_preserves_custom_build_profile(self):
        audit = unittest.mock.Mock()
        save_validation_execution_evidence(
            audit,
            1,
            "cmhelper_pc_agent_auth",
            {"exit_code": 0, "commands": [["python", "-m", "unittest"]], "stdout": "ok", "stderr": ""},
            {"exit_code": 0, "stdout": "built", "stderr": ""},
            build_profile="cmhelper_pc_agent_auth_build",
        )
        filename, payload = audit.save_json.call_args.args
        self.assertEqual(filename, "validation_execution_i1.json")
        self.assertEqual(payload["test_profile"], "cmhelper_pc_agent_auth")
        self.assertEqual(payload["build_profile"], "cmhelper_pc_agent_auth_build")


if __name__ == "__main__":
    unittest.main()
