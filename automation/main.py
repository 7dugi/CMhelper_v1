import os
import sys
import json
import subprocess
from datetime import datetime

# Set up utf-8 encoding for stdout/stderr to prevent cp949 crash on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from automation.config import PROJECT_ROOT, HARNESS_MODE, MAX_AUTONOMOUS_REVIEW_ITERATIONS
from automation.models import Task, TaskState, RiskLevel, TaskContext, SeniorPlan, ImplementationResult, ReviewResult, ValidationResult, ReviewStatus, ValidationStatus
from automation.governance import GovernanceLoader
from automation.cli_runner import CLIRunner
from automation.adapters.codex_adapter import CodexAdapter
from automation.adapters.antigravity_adapter import AntigravityAdapter
from automation.audit_logger import AuditLogger
from automation.orchestrator import Orchestrator
from automation.evidence_executor import EvidenceExecutor
from automation.permission_manager import PermissionManager

def to_dict(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()

def main():
    if HARNESS_MODE != "H2_REAL_READ_ONLY":
        print("Error: HARNESS_MODE must be H2_REAL_READ_ONLY for this run.")
        sys.exit(1)

    task_id = "H3-INTEGRATED-004"
    audit = AuditLogger(task_id)
    runner = CLIRunner()
    executor = EvidenceExecutor()
    permission_manager = PermissionManager()

    # 1. Preflight
    audit.log_event("TASK_STARTED", {"task_id": task_id})
    executor.capture_baseline()
    git_before = executor.capture_repo_snapshot()
    audit.save_text("git_before.json", json.dumps({"snapshot": git_before}))

    task = Task(
        id=task_id,
        title="README Implementer Tool Boundary Update",
        description="""automation/README.md의 "Implementer Tool Boundary" 또는 이에 해당하는 기존 설명을 확인하고 다음 원칙이 명확하게 설명되도록 중복 없이 최소 수정하라.
1. Implementer는 trusted workspace 내부 파일을 built-in file tools로 읽고 수정한다.
2. Implementer는 shell/git/rg/pytest/npm/MCP/Vercel을 직접 실행하지 않는다.
3. Git/Test/Build Evidence는 Harness EvidenceExecutor가 수집한다.
4. AI-generated arbitrary command는 실행하지 않는다.
5. Codex Senior가 승인한 Mutation Scope 밖의 파일 변경은 허용하지 않는다.
6. Codex Review + Validation + PassGate가 모두 PASS한 뒤 READY_TO_COMMIT 상태가 된다.
7. 실제 Commit/Push는 User Approval 이후 단계다.

기존 내용과 중복되지 않게 최소 변경으로 명확하게 보완한다.
만약 파일 끝에 '<!-- H3_WRITE_PERMISSION_SMOKE_TEST -->' 가 있다면 제거한다.""",
        state=TaskState.PRE_FLIGHT
    )

    # 2. Governance
    loader = GovernanceLoader()
    docs = loader.load_core_documents()
    audit.save_json("governance.json", {k: {"path": v.path, "exists": v.exists, "loaded": v.loaded, "sha256": v.sha256} for k, v in docs.items()})

    context = TaskContext(
        task=task,
        repository_root=PROJECT_ROOT,
        branch="feature/dev-harness-v1",
        head="HEAD",
        loaded_documents=docs
    )

    codex = CodexAdapter()
    agy = AntigravityAdapter()
    orchestrator = Orchestrator(context)
    orchestrator.load_context()

    # 3. Senior Plan
    print("Running Codex Senior Planning...")
    orchestrator.create_plan()
    
    plan_prompt = f"""Task: {task.description}
Current Repository State: Baseline snapshot taken.
Tool Boundary: Antigravity can use built-in file tools ONLY. No shell commands.
H3 Risk Policy: Keep risk GREEN. Limit allowed_mutation_paths to the absolute minimum necessary files.
Please output a Structured JSON matching the SeniorPlan schema.
IMPORTANT FOR allowed_mutation_paths: You MUST include "automation/README.md" in this list since the task explicitly requires modifying it.
IMPORTANT FOR required_validations: You MUST output exactly ["DOC_ONLY", "HARNESS_TEST"]. Do NOT write descriptive sentences, and do NOT use the word 'git' or 'pytest' as it will crash the Pydantic validator."""

    plan_cmd = codex.build_plan_command(plan_prompt)
    plan_raw = runner.run(plan_cmd)
    audit.save_text("senior_plan_raw.txt", f"STDOUT:\n{plan_raw['stdout']}\nSTDERR:\n{plan_raw['stderr']}")

    try:
        plan_data = json.loads(plan_raw["stdout"])
        senior_plan = SeniorPlan(**plan_data)
        audit.save_json("senior_plan.json", to_dict(senior_plan))
    except Exception as e:
        print(f"Codex Plan Parsing failed: {str(e)}")
        sys.exit(1)

    # Senior Plan validation
    if not senior_plan.allowed_mutation_paths:
        print("FAIL: allowed_mutation_paths is empty.")
        sys.exit(1)
    if "automation/README.md" not in senior_plan.allowed_mutation_paths:
        print("FAIL: automation/README.md not in allowed_mutation_paths.")
        sys.exit(1)

    # 4. Permission Manager
    print(f"Applying permissions for {senior_plan.allowed_mutation_paths}")
    audit.save_json("permission_before.json", {"paths": senior_plan.allowed_mutation_paths})
    if not permission_manager.apply_scoped_permissions(senior_plan.allowed_mutation_paths):
        print("FAIL: Could not apply scoped permissions.")
        sys.exit(1)
    audit.save_json("permission_applied.json", {"success": True})

    try:
        iteration = 0
        review_status = ReviewStatus.REVISE
        previous_issues = frozenset()
        review_iterations_log = []

        while review_status == ReviewStatus.REVISE and iteration < MAX_AUTONOMOUS_REVIEW_ITERATIONS:
            iteration += 1
            print(f"\n--- Autonomous Loop Iteration {iteration} ---")
            
            # Transition to REVISING if we are looping back from REVIEWING
            if orchestrator.sm.current_state == TaskState.REVIEWING:
                orchestrator.sm.transition(TaskState.REVISING)
            
            # 5. Antigravity Implementation
            orchestrator.request_implementation()
            impl_prompt = f"""REAL MUTATION TASK.
Task: {task.description}
Senior Plan Summary: {senior_plan.summary}
Allowed Mutation Paths: {senior_plan.allowed_mutation_paths}
Scope: {senior_plan.scope}
Acceptance Criteria: {[c.description for c in senior_plan.acceptance_criteria]}

Execute the task using ONLY built-in file methods. Modify ONLY the allowed_mutation_paths.
Return findings as valid JSON ImplementationResult."""

            if iteration > 1:
                impl_prompt += f"\nPrevious Review Feedback: {list(previous_issues)}"

            impl_cmd = agy.build_command(impl_prompt)
            impl_raw = runner.run(impl_cmd)
            
            if "auto-denied" in impl_raw['stderr']:
                print("FAIL: auto-denied detected. Permission manager failed to authorize write.")
                sys.exit(1)

            if impl_raw['exit_code'] != 0:
                print("FAIL: Antigravity exited with error.")
                sys.exit(1)

            try:
                raw_out = impl_raw["stdout"].strip()
                if raw_out.startswith("```json"):
                    raw_out = raw_out.split("```json")[1].split("```")[0].strip()
                elif "{" in raw_out:
                    raw_out = raw_out[raw_out.find("{"):raw_out.rfind("}")+1]
                impl_result = ImplementationResult(**json.loads(raw_out))
                audit.save_json(f"implementation_result_i{iteration}.json", to_dict(impl_result))
            except Exception as e:
                print(f"Antigravity Impl Parsing failed: {str(e)}")
                sys.exit(1)

            # 6. Baseline-aware Mutation Guard
            actual_delta = executor.get_actual_new_mutation()
            audit.save_json(f"git_delta_i{iteration}.json", {"actual_new_mutation": actual_delta})
            git_diff = executor.capture_git_diff()
            
            for changed_file in actual_delta:
                if changed_file.replace("\\", "/") not in [p.replace("\\", "/") for p in senior_plan.allowed_mutation_paths]:
                    print(f"FAIL: UNEXPECTED_MUTATION. File {changed_file} is outside allowed paths.")
                    sys.exit(1)

            # 7. Validation
            print("Running Harness Validations...")
            test_res = subprocess.run(["python", "-m", "unittest", "discover", "-s", "automation/tests"], cwd=PROJECT_ROOT, capture_output=True, text=True)
            compile_res = subprocess.run(["python", "-m", "compileall", "automation/"], cwd=PROJECT_ROOT, capture_output=True, text=True)
            
            validation_result = ValidationResult(
                tests=ValidationStatus.PASS if test_res.returncode == 0 else ValidationStatus.FAIL,
                build=ValidationStatus.PASS if compile_res.returncode == 0 else ValidationStatus.FAIL
            )
            audit.save_json(f"validation_result_i{iteration}.json", to_dict(validation_result))

            if validation_result.tests == ValidationStatus.FAIL or validation_result.build == ValidationStatus.FAIL:
                print("FAIL: Harness Tests or Compileall failed.")
                sys.exit(1)

            # 8. Codex Review
            orchestrator.review_result()
            review_prompt = f"""Review Implementation.
Task: {task.description}
Implementation Summary: {impl_result.summary}
Actual Git Delta (Files changed): {actual_delta}
Git Diff: {git_diff[:2000]}
Validations: Tests {validation_result.tests.value}, Build {validation_result.build.value}
Has the task been fulfilled exactly as requested without violating rules?
Return JSON ReviewResult (status: PASS, REVISE, FAILED_STALLED)."""

            review_cmd = codex.build_review_command(review_prompt)
            review_raw = runner.run(review_cmd)
            
            try:
                review_result = ReviewResult(**json.loads(review_raw["stdout"]))
                review_iterations_log.append(to_dict(review_result))
                review_status = review_result.status
            except Exception as e:
                print(f"Codex Review Parsing failed: {str(e)}")
                sys.exit(1)

            orchestrator.handle_review_result(review_result)
            
            if review_status == ReviewStatus.REVISE:
                current_issues = frozenset(review_result.issues)
                if current_issues == previous_issues:
                    print("FAIL: No-progress detected. Same issues reported by reviewer.")
                    orchestrator.sm.transition(TaskState.FAILED_STALLED)
                    review_status = ReviewStatus.FAILED_STALLED
                    break
                previous_issues = current_issues

        audit.save_json("review_iterations.json", review_iterations_log)

        # 10. PassGate
        if review_status != ReviewStatus.PASS:
            print(f"FAIL: PassGate rejected. Final ReviewStatus: {review_status}")
            sys.exit(1)
            
    finally:
        # 9. Cleanup
        cleanup_success = permission_manager.restore_permissions()
        audit.save_json("permission_cleanup.json", {"success": cleanup_success})
        if not cleanup_success:
            print("FAIL: Permission cleanup failed.")
            sys.exit(1)

    orchestrator.sm.transition(TaskState.READY_TO_COMMIT)
    git_after = executor.capture_repo_snapshot()
    audit.save_text("git_after.json", json.dumps({"snapshot": git_after}))

    final_report = f"""# H3-INTEGRATED-001 Complete
State: {orchestrator.sm.current_state.value}
Mutation Guard: PASS
Permission Cleanup: PASS
Iterations: {iteration}
Final Review Status: PASS
"""
    audit.save_text("final_report.md", final_report)
    print("E2E H3-INTEGRATED-001 Run Completed Successfully.")

if __name__ == "__main__":
    main()
