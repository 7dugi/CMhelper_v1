import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Set up utf-8 encoding for stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from automation.config import PROJECT_ROOT, HARNESS_MODE, MAX_AUTONOMOUS_REVIEW_ITERATIONS
from automation.models import Task, TaskState, RiskLevel, TaskContext, SeniorPlan, ImplementationResult, ReviewResult, ValidationResult, ReviewStatus, ValidationStatus, ApprovalAction, BrowserQAScenario, BrowserQAStep
from automation.governance import GovernanceLoader
from automation.cli_runner import CLIRunner
from automation.adapters.codex_adapter import CodexAdapter
from automation.adapters.antigravity_adapter import AntigravityAdapter
from automation.adapters.vercel_adapter import VercelAdapter, VercelResult, VercelAccessMode
from automation.adapters.browser_adapter import BrowserAdapter, BrowserQAResult
from automation.adapters.supabase_adapter import SupabaseAdapter, DatabaseEvidence
from automation.audit_logger import AuditLogger
from automation.orchestrator import Orchestrator
from automation.evidence_executor import EvidenceExecutor
from automation.permission_manager import PermissionManager
from automation.isolated_workspace import IsolatedImplementerWorkspace
from automation.project_registry import ProjectRegistry
from automation.context_builder import ContextBuilder
from automation.runtime_state import RuntimeStateManager
from automation.approval_gate import ApprovalManager, ApprovalStatus
from automation.notifier import NotificationEvent, ConsoleNotifier, NotificationSeverity, dispatch_notification

def to_dict(model):
    # Audit evidence must be JSON-serializable. Browser QA results include
    # timezone-aware datetimes; Python-mode model_dump leaves those as datetime
    # objects and AuditLogger deliberately fails closed by not persisting a
    # partial artifact.
    return model.model_dump(mode="json") if hasattr(model, "model_dump") else model.dict()

READ_ONLY_MARKERS = ("read-only", "read only", "write permission", "write access", "approvals disabled")

def canonical_repo_paths(paths, repository_root=PROJECT_ROOT):
    """Canonicalize paths to repository-relative POSIX paths without accepting escapes."""
    root = Path(repository_root).resolve()
    canonical = set()
    for raw_path in paths:
        if not raw_path:
            continue
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            canonical.add(candidate.resolve().relative_to(root).as_posix())
        except ValueError:
            # Preserve an external path as an invalid sentinel so scope checks fail closed.
            canonical.add(f"__OUTSIDE_REPOSITORY__:{candidate.resolve()}")
    return canonical

def implementation_gate(implementation_result, actual_changes, allowed_paths):
    """Return (terminal_state, reason), or (None, None) when implementation is evidenced."""
    details = " ".join([implementation_result.summary] + [str(issue) for issue in implementation_result.issues]).lower()
    if implementation_result.user_decision_required or any(marker in details for marker in READ_ONLY_MARKERS):
        return TaskState.NEED_USER_DECISION, "Implementer requires write permission or a user decision before changes can be made"

    allowed = canonical_repo_paths(allowed_paths)
    reported = canonical_repo_paths(implementation_result.changed_files)
    actual = canonical_repo_paths(actual_changes)
    if allowed and (not reported or not actual):
        return TaskState.FAILED_STALLED, "Mutation task produced no reported and verified changed files"
    if allowed and (not reported.issubset(allowed) or not actual.issubset(allowed)):
        return TaskState.FAILED_STALLED, "Implementation changed files outside the approved mutation scope"
    if allowed and reported != actual:
        return TaskState.FAILED_STALLED, "Implementer reported changed files do not match verified repository changes"
    return None, None


def approved_takeover_changes(baseline_status, allowed_paths):
    """Return an exact, user-approved pre-existing mutation set or fail closed."""
    allowed = canonical_repo_paths(allowed_paths)
    existing = canonical_repo_paths(baseline_status.keys())
    if not allowed or not allowed.issubset(existing):
        raise ValueError("Approved takeover requires every allowed mutation path to already be dirty")
    return sorted(allowed)

def subprocess_gate(exit_code, stage_name):
    if exit_code != 0:
        return TaskState.FAILED_STALLED, f"{stage_name} command failed with exit code {exit_code}"
    return None, None

def commit_gate(senior_plan, implementation_result, actual_changes, validation_result, review_result):
    terminal_state, _ = implementation_gate(implementation_result, actual_changes, senior_plan.allowed_mutation_paths)
    if terminal_state is not None:
        return False
    if review_result.status != ReviewStatus.PASS or not review_result.evidence:
        return False
    return validation_result.all_required_passed(senior_plan.required_validations)


def requires_preview_invalid_credential_verification(task_description: str) -> bool:
    """Recognize only the explicitly approved, non-mutating negative-auth check."""
    normalized = (task_description or "").lower()
    return (
        "preview-only" in normalized
        and "fake invalid credential" in normalized
    )


def is_cmhelper_pc_agent_auth_task(task_description: str = "", allowed_mutation_paths: list = None, summary: str = "") -> bool:
    """Identify if the task corresponds to the Windows PC Agent authentication profile."""
    if allowed_mutation_paths:
        if any(p.startswith("CMhelper_agent/") or "agent" in p.lower() for p in allowed_mutation_paths):
            return True
    combined = f"{task_description or ''} {summary or ''}".lower()
    return any(k in combined for k in ("pc agent", "cmhelper_agent", "agent auth", "agent_auth", "cmhelper_pc_agent_auth"))


def validation_is_required(senior_plan: SeniorPlan, validation_name: str) -> bool:
    """Return whether the approved plan requires this validation category.

    Optional stages must not consume evidence produced only by a required
    Preview/UI workflow.  Keeping this check in one helper prevents a skipped
    Preview stage from later being treated as an implicit Browser QA request.
    """
    return validation_name in senior_plan.required_validations


def has_preview_invalid_credential_evidence(scenario_data, result_data) -> bool:
    """Fail closed unless the persisted QA evidence proves the bounded 401 flow."""
    if result_data.get("status") != "PASS":
        return False
    scenario_steps = scenario_data.get("steps", [])
    expected_actions = ["fill", "fill", "click", "assert_network_status", "assert_text"]
    if [step.get("action") for step in scenario_steps] != expected_actions:
        return False
    if scenario_steps[0].get("selector_or_target") != "input[type='email']":
        return False
    if scenario_steps[1].get("selector_or_target") != "input[type='password']":
        return False
    if scenario_steps[2].get("selector_or_target") != "button[type='submit']":
        return False
    if scenario_steps[3].get("selector_or_target") != "POST /api/auth/login" or scenario_steps[3].get("expected") != "401":
        return False
    if scenario_steps[4].get("selector_or_target") != "body" or scenario_steps[4].get("expected") != "Invalid credentials":
        return False
    result_steps = result_data.get("steps", [])
    return (
        len(result_steps) == len(expected_actions)
        and [step.get("action") for step in result_steps] == expected_actions
        and all(step.get("status") == "PASS" for step in result_steps)
        and "-> 401" in (result_steps[3].get("actual") or "")
        and "Invalid credentials" in (result_steps[4].get("actual") or "")
    )


MANUAL_PREVIEW_ACCEPTANCE_IDS = {
    "won_quote_0_blank_form",
    "won_quote_1_prefill_editable",
    "won_quote_multiple_select_prefill",
    "non_won_conversion_blocked",
    "cancel_close_back_no_creation",
    "manual_contract_add_regression",
}


def has_manual_preview_acceptance_evidence(audit_dir):
    """Accept only a complete, non-mutating user Preview acceptance record."""
    try:
        with open(Path(audit_dir) / "manual_preview_acceptance.json", "r", encoding="utf-8") as handle:
            evidence = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False, None
    checks = evidence.get("checks")
    if not isinstance(checks, dict):
        return False, None
    valid = (
        evidence.get("status") == "PASS"
        and evidence.get("save_action") == "NOT_CLICKED"
        and bool(evidence.get("preview_url"))
        and set(checks) == MANUAL_PREVIEW_ACCEPTANCE_IDS
        and all(checks.get(check) == "PASS" for check in MANUAL_PREVIEW_ACCEPTANCE_IDS)
    )
    return valid, evidence


def collect_verified_source_diff(verified_changed_files):
    """Read only the task-verified paths for evidence-based final review."""
    if not verified_changed_files:
        raise ValueError("No verified implementation paths are available for source evidence")
    result = subprocess.run(
        ["git", "diff", "--unified=3", "--", *verified_changed_files],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git source evidence collection failed with exit code {result.returncode}")
    if not result.stdout.strip():
        raise ValueError("Verified implementation paths have no readable source diff")
    return result.stdout


def execute_approved_push(approval_manager, state, git_executor):
    """Perform a real push only for the persisted, matching approved gate."""
    approval_id = state.blocking_approval_id
    approval = approval_manager.get_approval(approval_id) if approval_id else None
    if (
        approval is None
        or approval.task_id != state.task_id
        or approval.action != ApprovalAction.PUSH.value
        or approval.status != ApprovalStatus.APPROVED
        or not state.commit_sha
    ):
        raise RuntimeError("Approved PUSH gate is missing, mismatched, expired, or has no committed SHA")
    git_executor.push()
    return {
        "commit_sha": state.commit_sha,
        "branch": git_executor.get_current_branch(),
        "remote": "origin",
        "status": "PUSHED",
    }

def save_validation_evidence(audit, iteration, validation_result):
    audit.save_json(f"validation_result_i{iteration}.json", to_dict(validation_result))

def save_validation_execution_evidence(audit, iteration, test_profile, test_result, build_result, git_hygiene=None, build_profile=None):
    """Persist bounded command evidence so a fail-closed validation can be diagnosed."""
    def result_summary(result):
        return {
            "exit_code": result.get("exit_code"),
            "commands": result.get("commands", []),
            "stdout_tail": result.get("stdout", "")[-4000:],
            "stderr_tail": result.get("stderr", "")[-4000:],
        }

    payload = {
        "test_profile": test_profile,
        "build_profile": build_profile or "cmhelper_phase3d_frontend_build",
        "tests": result_summary(test_result),
        "build": result_summary(build_result),
    }
    if git_hygiene is not None:
        payload["git_hygiene"] = {
            "diff_check_exit_code": git_hygiene["diff_check"]["exit_code"],
            "diff_check_stderr": git_hygiene["diff_check"]["stderr"],
            "status_exit_code": git_hygiene["status"]["exit_code"],
            "status_output": git_hygiene["status"]["stdout"],
        }
    audit.save_json(f"validation_execution_i{iteration}.json", payload)

def load_pre_review_evidence(audit, iteration):
    """Restore evidence required when a Worker resumes after validation."""
    def load_json(filename):
        with open(os.path.join(audit.report_dir, filename), "r", encoding="utf-8") as handle:
            return json.load(handle)

    evidence_iteration = next(
        (
            candidate for candidate in range(iteration, 0, -1)
            if all(
                (Path(audit.report_dir) / f"{prefix}_i{candidate}.json").is_file()
                for prefix in (
                    "implementation_result", "implementation_evidence", "validation_result",
                    "validation_execution", "harness_compileall",
                )
            )
        ),
        None,
    )
    if evidence_iteration is None:
        raise RuntimeError("No complete implementation and validation evidence set is available for review resume")

    senior_plan = SeniorPlan(**load_json("senior_plan.json"))
    implementation_result = ImplementationResult(**load_json(f"implementation_result_i{evidence_iteration}.json"))
    implementation_evidence = load_json(f"implementation_evidence_i{evidence_iteration}.json")
    validation_result = ValidationResult(**load_json(f"validation_result_i{evidence_iteration}.json"))
    execution = load_json(f"validation_execution_i{evidence_iteration}.json")
    compile_result = load_json(f"harness_compileall_i{evidence_iteration}.json")
    review_result = ReviewResult(**load_json(f"review_result_i{evidence_iteration}.json"))
    hygiene = execution.get("git_hygiene")
    if not hygiene:
        raise RuntimeError("Review resume requires persisted Git hygiene evidence")
    git_hygiene = {
        "diff_check": {"exit_code": hygiene["diff_check_exit_code"], "stderr": hygiene.get("diff_check_stderr", "")},
        "status": {"exit_code": hygiene["status_exit_code"], "stdout": hygiene.get("status_output", "")},
    }
    return (
        senior_plan,
        implementation_result,
        implementation_evidence["verified_changed_files"],
        validation_result,
        execution["test_profile"],
        execution["tests"],
        execution.get("build_profile", "cmhelper_phase3d_frontend_build"),
        execution["build"],
        compile_result,
        git_hygiene,
        review_result,
    )

def load_pre_validation_evidence(audit, iteration):
    """Restore the approved implementation delta when validation is retried."""
    def load_json(filename):
        with open(os.path.join(audit.report_dir, filename), "r", encoding="utf-8") as handle:
            return json.load(handle)

    senior_plan = SeniorPlan(**load_json("senior_plan.json"))
    implementation_result = ImplementationResult(**load_json(f"implementation_result_i{iteration}.json"))
    implementation_evidence = load_json(f"implementation_evidence_i{iteration}.json")
    actual_changes = implementation_evidence["verified_changed_files"]
    terminal_state, reason = implementation_gate(
        implementation_result, actual_changes, senior_plan.allowed_mutation_paths
    )
    if terminal_state is not None:
        raise RuntimeError(f"Persisted implementation evidence is not valid for retry: {reason}")
    return senior_plan, implementation_result, actual_changes

def notify_terminal_block(task_id, project_id, event_type, message, severity):
    dispatch_notification(NotificationEvent(
        event_type=event_type,
        message=message,
        task_id=task_id,
        project_id=project_id,
        severity=severity,
        send_to_discord=True,
    ))

def build_planning_prompt(task_description, repository_context=None):
    """Build a read-only planning prompt with the Harness-loaded evidence.

    The Planner has no filesystem tool by design.  Passing the already-loaded
    context bundle is therefore required for evidence-based planning; otherwise
    it can only fail closed without identifying a valid mutation scope.
    """
    context_json = json.dumps(repository_context or {}, ensure_ascii=False)
    return (
        f"Task: {task_description}\n"
        f"Harness-loaded repository context: {context_json}\n"
        "Role: You are the Senior Planner. Your environment is intentionally read-only. "
        "Read-only planning access is normal and must never be used to infer that the Antigravity "
        "Implementer cannot write. The Implementer workspace capability is decided only by the "
        "Antigravity Implementer and PermissionManager scoped-write gate.\n"
        "Create a concrete implementation plan from repository evidence. Set user_decision_required "
        "to true only for a genuine missing user decision, requirement ambiguity, policy conflict, or "
        "risk requiring human approval—not because your planning sandbox is read-only.\n"
        "Tool Boundary: Only built-in file tools allowed. Please output a Structured JSON matching the "
        "SeniorPlan schema. required_validations must contain only validation category keys from the "
        "schema (for example: tests, build); never include shell commands, command lines, or file paths."
    )

def build_implementation_prompt(senior_plan, allowed_mutation_paths, revision_issues=None):
    """Build a bounded mutation brief from the approved plan, not raw task history."""
    brief = {
        "summary": senior_plan.summary,
        "scope": senior_plan.scope,
        "out_of_scope": senior_plan.out_of_scope,
        "acceptance_criteria": [to_dict(item) for item in senior_plan.acceptance_criteria],
        "revision_issues": revision_issues or [],
    }
    return (
        "REAL MUTATION TASK.\n"
        "The following Senior-approved implementation brief is authoritative. "
        "Repository governance and architecture documents named in the brief remain source of truth; "
        "do not infer permission to broaden scope.\n"
        f"Implementation brief: {json.dumps(brief, ensure_ascii=False)}\n"
        f"Allowed Mutation Paths: {allowed_mutation_paths}\n"
        "Role boundary: Modify only files in Allowed Mutation Paths, then return exactly one valid JSON "
        "ImplementationResult object matching the supplied JSON Schema. It must include summary (string) and "
        "changed_files (array of repository-relative paths); include issues as an array and "
        "user_decision_required as a boolean when applicable. changed_files must contain only files newly created or whose content was changed "
        "during this Antigravity invocation. Do not include files that were already dirty before this invocation unless "
        "you changed their content during this invocation. Do not wrap it in Markdown or include explanatory text. "
        "Do not run or request any validation or command execution. "
        "Forbidden: pytest, unittest, compileall, npm test, build, shell, PowerShell, bash, "
        "or any terminal command. The Harness VALIDATING stage exclusively runs tests and "
        "verification; validation failures are handled by the Harness and reviewers."
    )

def build_senior_review_prompt(senior_plan, implementation_result, actual_changes, allowed_paths,
                               validation_result, test_profile, test_res, build_profile, build_res,
                               compile_res, git_hygiene, task_description=""):
    """Build the evidence-only review for stages completed before Preview/UI.

    Preview and Browser QA run after this review and remain mandatory at Final
    Review.  They must not cause a code-revision loop before the Harness has
    had a chance to execute them.
    """
    return (
        "Review the supplied Harness evidence only. Do not run pytest, unittest, build, shell, "
        "PowerShell, bash, or any other validation command in this read-only reviewer sandbox. "
        "Harness VALIDATING is the sole authority for product-test execution; its successful exit "
        "codes below must not be overturned by this sandbox's filesystem or TEMP permissions. "
        "Do not assume PASS. Return PASS only when reported and verified invocation changes match "
        "each other, are subsets of allowed mutation paths, and the completed Harness validation evidence "
        "supports the result. Preview and Browser/UI validation are later mandatory Harness stages; "
        "do not return REVISE merely because they are NOT_RUN at this pre-preview review. Final Review "
        "must still require every validation category in the Senior Plan to pass. Allowed mutation paths "
        "are task-wide scope, not a requirement that every later invocation repeat every pre-existing "
        "approved dirty change. Do not return REVISE for missing git hygiene evidence when the supplied "
        "Harness git_hygiene object contains it. The user-approved task objective below is authoritative "
        "for the intended outcome. If a plan example names only some malformed syntax locations, do not "
        "reject a necessary, behavior-preserving syntax repair within the allowed path merely because that "
        "example was not exhaustive. Still return REVISE for product-behavior changes, scope violations, "
        "or evidence that does not support the stated task objective.\n"
        f"Task objective: {task_description}\n"
        f"Senior plan: {json.dumps(to_dict(senior_plan), ensure_ascii=False)}\n"
        f"Implementation result: {json.dumps(to_dict(implementation_result), ensure_ascii=False)}\n"
        f"Verified changed files: {json.dumps(actual_changes, ensure_ascii=False)}\n"
        f"Allowed task scope: {json.dumps(allowed_paths, ensure_ascii=False)}\n"
        f"Validation result: {json.dumps(to_dict(validation_result), ensure_ascii=False)}\n"
        f"Harness validation execution: {json.dumps({'test_profile': test_profile, 'tests_exit_code': test_res['exit_code'], 'build_profile': build_profile, 'build_exit_code': build_res['exit_code'], 'build_commands': build_res.get('commands', []), 'compileall_exit_code': compile_res['exit_code'], 'git_hygiene': git_hygiene}, ensure_ascii=False)}"
    )

def parse_implementation_result(raw_output):
    """Extract exactly one schema-valid ImplementationResult object from CLI output."""
    decoder = json.JSONDecoder()
    candidates = []
    for index, character in enumerate(raw_output):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(raw_output[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            candidates.append(ImplementationResult(**payload))
        except Exception:
            continue
    if len(candidates) != 1:
        raise ValueError("Expected exactly one schema-valid ImplementationResult JSON object")
    return candidates[0]

def planner_requires_user_decision(senior_plan):
    """Only the planner's explicit requirement/policy decision controls this gate."""
    return senior_plan.user_decision_required

def main():
    if HARNESS_MODE not in {"H2_REAL_READ_ONLY", "H2_SYNTHETIC_E2E"}:
        print("Error: HARNESS_MODE must be H2_REAL_READ_ONLY for this run.")
        sys.exit(1)

    task_id = os.environ.get("HARNESS_TASK_ID")
    project_id = os.environ.get("HARNESS_PROJECT_ID", "cmhelper")
    if not task_id:
        print("Error: HARNESS_TASK_ID not set.")
        sys.exit(1)

    runtime = RuntimeStateManager(PROJECT_ROOT)
    state = runtime.load_state()
    if not state or state.task_id != task_id:
        print(f"Error: Runtime state does not match task {task_id}.")
        sys.exit(1)

    audit = AuditLogger(task_id)
    runner = CLIRunner()
    executor = EvidenceExecutor()
    permission_manager = PermissionManager()
    approval_mgr = ApprovalManager(PROJECT_ROOT)
    notifier = ConsoleNotifier()

    task = Task(
        id=task_id,
        title=state.task_title,
        description=state.task_description,
        state=state.state
    )

    registry = ProjectRegistry(PROJECT_ROOT)
    config = registry.get_project(project_id)
    if not config:
        print(f"Error: Project Config not found for {project_id}.")
        sys.exit(1)

    ctx_builder = ContextBuilder(PROJECT_ROOT)
    bundle = ctx_builder.build_context(config, str(registry.projects_dir))
    
    # Save bundle to audit for reference
    audit.save_json("context_bundle.json", bundle)

    context = TaskContext(
        task=task,
        repository_root=config.resolve_root(str(registry.projects_dir)),
        branch=config.development_branch,
        head="HEAD",
        loaded_documents={}
    )

    orchestrator = Orchestrator(context)
    codex = CodexAdapter()
    agy = AntigravityAdapter()
    senior_plan = None
    implementation_result = None
    actual_changes = []
    validation_result = None

    # A resumed Worker is a new process.  Every post-validation stage needs
    # the persisted plan and validation evidence rather than in-memory values
    # from the original Worker invocation.
    post_validation_resume_stages = {
        TaskState.REVIEWING,
        TaskState.DB_INSPECTION,
        TaskState.PREVIEW_DEPLOY,
        TaskState.BROWSER_QA_PLANNING,
        TaskState.BROWSER_QA_EXECUTION,
        TaskState.FINAL_REVIEW,
    }
    if state.state == TaskState.RESUMING and state.resume_stage == TaskState.VALIDATING:
        try:
            senior_plan, implementation_result, actual_changes = load_pre_validation_evidence(audit, state.iteration)
        except Exception as exc:
            state.state = TaskState.FAILED_STALLED
            state.reason = f"Validation resume evidence could not be restored: {exc}"
            runtime.save_state(state)
            return
    elif state.state == TaskState.RESUMING and state.resume_stage in post_validation_resume_stages:
        try:
            (
                senior_plan, implementation_result, actual_changes, validation_result,
                test_profile, test_res, build_profile, build_res, compile_res, git_hygiene,
                review_result,
            ) = load_pre_review_evidence(audit, state.iteration)
        except Exception as exc:
            state.state = TaskState.FAILED_STALLED
            state.reason = f"Post-validation resume evidence could not be restored: {exc}"
            runtime.save_state(state)
            return


    while state.state not in [
        TaskState.WAITING_FOR_USER_APPROVAL,
        TaskState.WAITING_FOR_QUOTA,
        TaskState.FAILED_STALLED,
        TaskState.REJECTED_BY_USER,
        TaskState.COMPLETED,
        TaskState.NEED_USER_DECISION
    ]:
        print(f"\n--- Executing Stage: {state.state.value} ---")
        
        if state.state == TaskState.QUEUED:
            audit.log_event("TASK_STARTED", {"task_id": task_id})
            state.state = TaskState.PRE_FLIGHT
            
        elif state.state == TaskState.PRE_FLIGHT:
            state.state = TaskState.CONTEXT_LOADING
            
        elif state.state == TaskState.CONTEXT_LOADING:
            state.state = TaskState.PLANNING
            
        elif state.state == TaskState.PLANNING:
            print("Running Codex Senior Planning...")
            plan_prompt = build_planning_prompt(task.description, bundle)
            plan_cmd = codex.build_plan_command(plan_prompt)
            plan_raw = runner.run(plan_cmd)
            audit.save_json("planning_cli_result.json", {
                "exit_code": plan_raw["exit_code"],
                "timed_out": plan_raw["timed_out"],
                "stderr": plan_raw["stderr"],
                "stdout": plan_raw["stdout"],
            })

            if plan_raw["exit_code"] != 0:
                print(f"Codex planning exited with code {plan_raw['exit_code']}.")
                state.state = TaskState.FAILED_STALLED
                state.reason = f"Codex planning command failed with exit code {plan_raw['exit_code']}"
                break
            
            try:
                plan_data = json.loads(plan_raw["stdout"])
                senior_plan = SeniorPlan(**plan_data)
                audit.save_json("senior_plan.json", to_dict(senior_plan))
                state.allowed_mutation_paths = senior_plan.allowed_mutation_paths
            except Exception as e:
                print(f"Codex Plan Parsing failed: {str(e)}")
                state.state = TaskState.FAILED_STALLED
                state.reason = "Codex planning output failed schema parsing"
                break

            if planner_requires_user_decision(senior_plan):
                state.state = TaskState.NEED_USER_DECISION
                state.reason = "Senior planning requires a user decision before implementation"
                runtime.save_state(state)
                break
            
            state.state = TaskState.IMPLEMENTING
            state.iteration = 1
            state.last_successful_stage = TaskState.PLANNING
            
        elif state.state == TaskState.IMPLEMENTING:
            # Capture after planning/permission setup so pre-existing dirty files are not attributed to this run.
            executor.capture_baseline()
            if state.takeover_existing_changes:
                try:
                    actual_changes = approved_takeover_changes(executor.baseline_status, state.allowed_mutation_paths)
                except ValueError as exc:
                    state.state = TaskState.FAILED_STALLED
                    state.reason = str(exc)
                    runtime.save_state(state)
                    break
                implementation_result = ImplementationResult(
                    summary="User-approved takeover of the existing allowed Phase implementation diff for validation",
                    changed_files=actual_changes,
                )
                audit.save_json(f"implementation_result_i{state.iteration}.json", to_dict(implementation_result))
                audit.save_json(f"implementation_evidence_i{state.iteration}.json", {
                    "reported_changed_files": implementation_result.changed_files,
                    "verified_changed_files": actual_changes,
                    "allowed_mutation_paths": state.allowed_mutation_paths,
                    "mode": "USER_APPROVED_TAKEOVER",
                })
                terminal_state, reason = implementation_gate(implementation_result, actual_changes, state.allowed_mutation_paths)
                if terminal_state is not None:
                    state.state = terminal_state
                    state.reason = reason
                    runtime.save_state(state)
                    break
                state.takeover_existing_changes = False
                state.state = TaskState.VALIDATING
                state.last_successful_stage = TaskState.IMPLEMENTING
                runtime.save_state(state)
                continue
            isolated_workspace = IsolatedImplementerWorkspace(PROJECT_ROOT, task_id, state.iteration)
            try:
                workspace_root = isolated_workspace.create(state.allowed_mutation_paths)
                isolated_workspace.capture_source_fingerprints(state.allowed_mutation_paths)
                workspace_executor = EvidenceExecutor(str(workspace_root))
                workspace_executor.capture_baseline()
                readable_paths = workspace_executor.get_tracked_repository_files()
            except Exception as exc:
                state.state = TaskState.FAILED_STALLED
                state.reason = str(exc)
                runtime.save_state(state)
                isolated_workspace.cleanup()
                break
            if senior_plan is None:
                try:
                    with open(os.path.join(audit.report_dir, "senior_plan.json"), "r", encoding="utf-8") as handle:
                        senior_plan = SeniorPlan(**json.load(handle))
                except Exception as exc:
                    state.state = TaskState.FAILED_STALLED
                    state.reason = f"Implementation resume requires persisted SeniorPlan evidence: {exc}"
                    runtime.save_state(state)
                    isolated_workspace.cleanup()
                    break
            revision_issues = []
            if state.iteration > 1:
                try:
                    with open(os.path.join(audit.report_dir, "final_review_result.json"), "r", encoding="utf-8") as handle:
                        prior_final_review = ReviewResult(**json.load(handle))
                    if prior_final_review.status != ReviewStatus.REVISE or not prior_final_review.issues:
                        raise ValueError("A revision iteration requires persisted Final Review issues")
                    revision_issues = prior_final_review.issues
                except Exception as exc:
                    state.state = TaskState.FAILED_STALLED
                    state.reason = f"Implementation revision requires Final Review feedback: {exc}"
                    runtime.save_state(state)
                    isolated_workspace.cleanup()
                    break
            impl_prompt = build_implementation_prompt(senior_plan, state.allowed_mutation_paths, revision_issues)
            impl_cmd = agy.build_command(impl_prompt, str(workspace_root))
            if not permission_manager.apply_scoped_permissions(state.allowed_mutation_paths, readable_paths, str(workspace_root)):
                state.state = TaskState.NEED_USER_DECISION
                state.reason = "Scoped implementer write permission could not be applied"
                notify_terminal_block(task_id, project_id, "IMPLEMENTER_PERMISSION_REQUIRED", state.reason, NotificationSeverity.ACTION_REQUIRED)
                runtime.save_state(state)
                isolated_workspace.cleanup()
                break
            try:
                impl_raw = runner.run(impl_cmd, allowed_workspace=str(workspace_root))
            finally:
                permission_manager.restore_permissions()
            audit.save_json(f"implementation_cli_result_i{state.iteration}.json", {
                "exit_code": impl_raw["exit_code"],
                "timed_out": impl_raw["timed_out"],
                "stderr": impl_raw["stderr"],
                "stdout": impl_raw["stdout"],
            })
            
            terminal_state, reason = subprocess_gate(impl_raw["exit_code"], "Implementer")
            if terminal_state is not None:
                print("Antigravity exited with error.")
                state.state = terminal_state
                state.reason = reason
                isolated_workspace.cleanup()
                break

            try:
                implementation_result = parse_implementation_result(impl_raw["stdout"])
                actual_changes = workspace_executor.get_actual_new_mutation()
                audit.save_json(f"implementation_result_i{state.iteration}.json", to_dict(implementation_result))
                audit.save_json(f"implementation_evidence_i{state.iteration}.json", {
                    "reported_changed_files": implementation_result.changed_files,
                    "verified_changed_files": actual_changes,
                    "allowed_mutation_paths": state.allowed_mutation_paths,
                    "mode": "ISOLATED_IMPLEMENTER_WORKSPACE",
                })
            except Exception as e:
                print(f"Implementation parsing failed: {str(e)}")
                state.state = TaskState.FAILED_STALLED
                state.reason = "Implementer output failed ImplementationResult schema parsing"
                isolated_workspace.cleanup()
                break

            terminal_state, reason = implementation_gate(implementation_result, actual_changes, state.allowed_mutation_paths)
            if terminal_state is not None:
                state.state = terminal_state
                state.reason = reason
                severity = NotificationSeverity.ACTION_REQUIRED if terminal_state == TaskState.NEED_USER_DECISION else NotificationSeverity.ERROR
                notify_terminal_block(task_id, project_id, "IMPLEMENTATION_BLOCKED", reason, severity)
                runtime.save_state(state)
                isolated_workspace.cleanup()
                break

            try:
                isolated_workspace.apply_verified_changes(actual_changes)
            except RuntimeError as exc:
                state.state = TaskState.FAILED_STALLED
                state.reason = f"Isolated implementation reconciliation failed: {exc}"
                runtime.save_state(state)
                isolated_workspace.cleanup()
                break
            isolated_workspace.cleanup()
                
            state.state = TaskState.VALIDATING
            state.last_successful_stage = TaskState.IMPLEMENTING
            
        elif state.state == TaskState.VALIDATING:
            print("Running Harness Validations (EvidenceExecutor)...")
            try:
                is_agent_auth = is_cmhelper_pc_agent_auth_task(
                    task.description,
                    senior_plan.allowed_mutation_paths if senior_plan else None,
                    senior_plan.summary if senior_plan else "",
                )
                if project_id == "cmhelper" and is_agent_auth:
                    test_profile = "cmhelper_pc_agent_auth" if "tests" in senior_plan.required_validations else "harness_tests"
                    build_profile = "cmhelper_pc_agent_auth_build" if "build" in senior_plan.required_validations else "compileall"
                elif project_id == "cmhelper":
                    test_profile = "cmhelper_phase3d_backend" if "tests" in senior_plan.required_validations else "harness_tests"
                    build_profile = "cmhelper_phase3d_frontend_build" if "build" in senior_plan.required_validations else "compileall"
                else:
                    test_profile = "harness_tests"
                    build_profile = "compileall"

                test_res = executor.run_tests(test_profile)
                build_res = executor.run_tests(build_profile)
                compile_res = executor.run_tests("compileall")
                git_hygiene = executor.run_git_hygiene()
                
                validation_result = ValidationResult(
                    tests=ValidationStatus.PASS if test_res["exit_code"] == 0 else ValidationStatus.FAIL,
                    build=ValidationStatus.PASS if build_res["exit_code"] == 0 else ValidationStatus.FAIL
                )
                save_validation_evidence(audit, state.iteration, validation_result)
                save_validation_execution_evidence(audit, state.iteration, test_profile, test_res, build_res, git_hygiene, build_profile=build_profile)
                audit.save_json(f"harness_compileall_i{state.iteration}.json", compile_res)
                
                if validation_result.tests == ValidationStatus.FAIL or validation_result.build == ValidationStatus.FAIL or compile_res["exit_code"] != 0 or git_hygiene["diff_check"]["exit_code"] != 0 or git_hygiene["status"]["exit_code"] != 0:
                    print("Required product validation or Harness compileall failed.")
                    state.resume_stage = TaskState.VALIDATING
                    state.state = TaskState.FAILED_STALLED
                    state.reason = "Required harness test or build validation failed"
                    break
                    
                state.state = TaskState.REVIEWING
                state.last_successful_stage = TaskState.VALIDATING
            except Exception as e:
                print(f"Validation failed: {e}")
                state.state = TaskState.FAILED_STALLED
                break
            
        elif state.state == TaskState.REVIEWING:
            print("Running Review...")
            if senior_plan is None or implementation_result is None or validation_result is None:
                try:
                    (
                        senior_plan, implementation_result, actual_changes, validation_result,
                        test_profile, test_res, build_profile, build_res, compile_res, git_hygiene,
                    ) = load_pre_review_evidence(audit, state.iteration)
                except Exception as exc:
                    state.state = TaskState.FAILED_STALLED
                    state.reason = f"Review resume evidence could not be restored: {exc}"
                    break
            review_prompt = build_senior_review_prompt(
                senior_plan, implementation_result, actual_changes, state.allowed_mutation_paths,
                validation_result, test_profile, test_res, build_profile, build_res, compile_res,
                git_hygiene, task.description,
            )
            review_cmd = codex.build_review_command(review_prompt)
            review_raw = runner.run(review_cmd)
            audit.save_json(f"review_cli_result_i{state.iteration}.json", {
                "exit_code": review_raw["exit_code"],
                "timed_out": review_raw["timed_out"],
                "stderr": review_raw["stderr"],
                "stdout": review_raw["stdout"],
            })

            terminal_state, reason = subprocess_gate(review_raw["exit_code"], "Review")
            if terminal_state is not None:
                state.state = terminal_state
                state.reason = reason
                break
            
            try:
                review_result = ReviewResult(**json.loads(review_raw["stdout"]))
                audit.save_json(f"review_result_i{state.iteration}.json", to_dict(review_result))
                if review_result.status.value == "PASS":
                    state.state = TaskState.DB_INSPECTION
                    state.last_successful_stage = TaskState.REVIEWING
                elif review_result.status.value == "REVISE":
                    if state.iteration >= MAX_AUTONOMOUS_REVIEW_ITERATIONS:
                        state.state = TaskState.FAILED_STALLED
                    else:
                        state.iteration += 1
                        state.state = TaskState.IMPLEMENTING
                elif review_result.status == ReviewStatus.NEED_USER_DECISION:
                    state.state = TaskState.NEED_USER_DECISION
                    state.reason = review_result.summary or "Reviewer requires a user decision"
                    notify_terminal_block(task_id, project_id, "REVIEW_USER_DECISION_REQUIRED", state.reason, NotificationSeverity.ACTION_REQUIRED)
                else:
                    state.state = TaskState.FAILED_STALLED
                    state.reason = review_result.summary or "Reviewer failed the implementation"
            except Exception as e:
                print(f"Review Parsing failed: {str(e)}")
                state.state = TaskState.FAILED_STALLED
                
        elif state.state == TaskState.RESUMING:
            print("\n--- Executing Stage: RESUMING ---")
            if state.resume_stage:
                state.state = state.resume_stage
            else:
                print("Error: resume_stage is None. Falling back to FAILED_STALLED to prevent unsafe resume.")
                state.state = TaskState.FAILED_STALLED

        elif state.state == TaskState.DB_INSPECTION:
            print("Running DB Inspection...")
            changed = executor.capture_changed_files()
            db_relevant = any(f.startswith("supabase/") for f in changed)
            database_required = "database" in senior_plan.required_validations
            if database_required and not config.supabase.enabled:
                state.state = TaskState.FAILED_STALLED
                state.reason = "Required database validation is not configured"
                break
            if database_required or (db_relevant and config.supabase.enabled):
                print("DB is relevant. Calling SupabaseAdapter.")
                try:
                    db_adapter = SupabaseAdapter()
                    db_evidence = db_adapter.inspect_db()
                    audit.save_json("database_evidence.json", to_dict(db_evidence))
                    audit.log_event("DB_INSPECTION_COMPLETED", {"status": "SUCCESS"})
                    validation_result.database = ValidationStatus.PASS
                except Exception as e:
                    print(f"DB Inspection failed: {e}")
                    state.state = TaskState.FAILED_STALLED
                    state.reason = "Required database validation failed"
                    break
            else:
                audit.log_event("DB_STAGE_SKIPPED", {"reason": "No DB relevance found"})
                validation_result.database = ValidationStatus.NOT_REQUIRED
            save_validation_evidence(audit, state.iteration, validation_result)
            
            state.state = TaskState.PREVIEW_DEPLOY
            state.last_successful_stage = TaskState.DB_INSPECTION
            
        elif state.state == TaskState.PREVIEW_DEPLOY:
            preview_required = validation_is_required(senior_plan, "preview")
            if not preview_required:
                # Optional preview availability must never invalidate a
                # backend-only task whose approved validation profile does
                # not require preview evidence.
                print("Preview is not required for this task. Skipping.")
                validation_result.preview = ValidationStatus.NOT_REQUIRED
                save_validation_evidence(audit, state.iteration, validation_result)
                state.state = TaskState.BROWSER_QA_PLANNING
                state.last_successful_stage = TaskState.PREVIEW_DEPLOY
                continue
            if not config.vercel.enabled:
                state.state = TaskState.FAILED_STALLED
                state.reason = "Required preview validation is not configured"
                break
                
            print("Running Vercel Preview Deploy...")
            try:
                vercel = VercelAdapter(PROJECT_ROOT, mode=VercelAccessMode.PREVIEW_DEPLOY)
                preview = vercel.trigger_preview_deploy()
                audit.save_json("vercel_preview.json", to_dict(preview))

                if preview.is_production:
                    print("SAFETY_BLOCK: Vercel deployment is Production, not Preview.")
                    state.state = TaskState.FAILED_STALLED
                    state.reason = "Production deployment not allowed for Browser QA."
                    runtime.save_state(state)
                    break
                if not preview.url or preview.status == "ERROR":
                    state.state = TaskState.FAILED_STALLED
                    state.reason = "Required preview validation did not return a usable preview"
                    runtime.save_state(state)
                    break
                validation_result.preview = ValidationStatus.PASS
                save_validation_evidence(audit, state.iteration, validation_result)

            except Exception as e:
                print(f"Vercel check failed: {e}")
                state.state = TaskState.FAILED_STALLED
                state.reason = "Required preview validation failed"
                break
            
            state.state = TaskState.BROWSER_QA_PLANNING
            state.last_successful_stage = TaskState.PREVIEW_DEPLOY
            
        elif state.state == TaskState.BROWSER_QA_PLANNING:
            ui_required = validation_is_required(senior_plan, "ui")
            if not ui_required:
                # Browser QA depends on Preview evidence.  A task that did not
                # require UI validation must not attempt to read a Preview
                # artifact that the preceding optional stage intentionally
                # skipped.
                print("Browser QA is not required for this task. Skipping.")
                validation_result.ui = ValidationStatus.NOT_REQUIRED
                save_validation_evidence(audit, state.iteration, validation_result)
                state.state = TaskState.FINAL_REVIEW
                state.last_successful_stage = TaskState.BROWSER_QA_PLANNING
                continue
            if not config.browser_qa.enabled:
                state.state = TaskState.FAILED_STALLED
                state.reason = "Required browser UI validation is not configured"
                break
                
            print("Running Browser QA Planning...")
            try:
                with open(os.path.join(audit.report_dir, "vercel_preview.json"), "r") as f:
                    preview_data = json.load(f)
                preview = VercelResult(**preview_data)
                
                if not preview.url or preview.is_production:
                    print("BROWSER_QA_CONFIGURATION_ERROR: Invalid or production URL.")
                    state.state = TaskState.FAILED_STALLED
                    runtime.save_state(state)
                    break
                    
                import urllib.parse
                parsed = urllib.parse.urlparse(preview.url)
                if parsed.scheme not in ["http", "https"] or not parsed.netloc:
                    print("BROWSER_QA_CONFIGURATION_ERROR: URL is not absolute.")
                    state.state = TaskState.FAILED_STALLED
                    runtime.save_state(state)
                    break
                
                # Safely join the route
                base_preview_url = preview.url.rstrip("/")
                start_url = base_preview_url + "/"
                
                if requires_preview_invalid_credential_verification(task.description):
                    # The task explicitly authorizes this negative-path check.
                    # It uses reserved fake values only; a successful login is
                    # neither attempted nor accepted as evidence.
                    scenario = BrowserQAScenario(
                        scenario_id=f"QA-{task_id}",
                        name="Preview fake-invalid-credential verification",
                        description="Submit a reserved fake credential and require POST /api/auth/login to reject it with 401.",
                        start_url=start_url,
                        risk="SAFE_INTERACTION",
                        steps=[
                            BrowserQAStep(action="fill", selector_or_target="input[type='email']", expected="migration-healthcheck@example.invalid", timeout=5000),
                            BrowserQAStep(action="fill", selector_or_target="input[type='password']", expected="not-a-real-password", timeout=5000),
                            BrowserQAStep(action="click", selector_or_target="button[type='submit']", timeout=5000),
                            # Preview functions can cold-start for longer than the
                            # generic UI wait.  Keep this negative request bounded
                            # while allowing the observed Preview startup window.
                            BrowserQAStep(action="assert_network_status", selector_or_target="POST /api/auth/login", expected="401", timeout=30000),
                            BrowserQAStep(action="assert_text", selector_or_target="body", expected="Invalid credentials", timeout=30000, screenshot_after=True),
                        ],
                    )
                else:
                    scenario = BrowserQAScenario(
                        scenario_id=f"QA-{task_id}",
                        name="Smoke test Vercel Preview",
                        description="Smoke test Vercel Preview",
                        start_url=start_url,
                        steps=[
                            BrowserQAStep(
                                # BrowserAdapter already navigates to start_url before
                                # executing steps. Verify that the loaded document has
                                # a body rather than issuing a redundant navigation.
                                action="wait_for_selector",
                                selector_or_target="body",
                                timeout=5000,
                                screenshot_after=True,
                            )
                        ]
                    )
                audit.save_json("browser_qa_scenario.json", to_dict(scenario))
                state.state = TaskState.BROWSER_QA_EXECUTION
                state.last_successful_stage = TaskState.BROWSER_QA_PLANNING
            except Exception as e:
                print(f"Browser QA Planning failed: {e}")
                state.state = TaskState.FAILED_STALLED
                runtime.save_state(state)
                break
            
        elif state.state == TaskState.BROWSER_QA_EXECUTION:
            print("Running Browser QA Execution...")
            try:
                browser = BrowserAdapter(PROJECT_ROOT)
                with open(os.path.join(audit.report_dir, "browser_qa_scenario.json"), "r") as f:
                    scenario_data = json.load(f)
                scenario = BrowserQAScenario(**scenario_data)
                qa_res = browser.run_scenario(task_id, scenario)
                audit.save_json("browser_qa_result.json", to_dict(qa_res))
                
                if qa_res.status == "FAIL":
                    print("Browser QA required scenario FAILED.")
                    state.state = TaskState.FAILED_STALLED
                    runtime.save_state(state)
                    break
                else:
                    validation_result.ui = ValidationStatus.PASS
                    save_validation_evidence(audit, state.iteration, validation_result)
                    state.state = TaskState.FINAL_REVIEW
                    state.last_successful_stage = TaskState.BROWSER_QA_EXECUTION
            except Exception as e:
                print(f"Browser QA execution failed: {e}")
                state.state = TaskState.FAILED_STALLED
                runtime.save_state(state)
                break
            
        elif state.state == TaskState.FINAL_REVIEW:
            print("Running Final Codex Review...")
            if validation_result is None or not validation_result.all_required_passed(senior_plan.required_validations):
                state.state = TaskState.FAILED_STALLED
                state.reason = "One or more required validations did not pass"
                break
            try:
                preview_required = validation_is_required(senior_plan, "preview")
                ui_required = validation_is_required(senior_plan, "ui")
                if preview_required:
                    with open(os.path.join(audit.report_dir, "vercel_preview.json"), "r", encoding="utf-8") as handle:
                        preview_evidence = json.load(handle)
                    if not preview_evidence.get("url") or preview_evidence.get("is_production"):
                        raise ValueError("Preview evidence is missing a non-production URL")
                else:
                    preview_evidence = {"status": "NOT_REQUIRED"}

                if ui_required:
                    with open(os.path.join(audit.report_dir, "browser_qa_result.json"), "r", encoding="utf-8") as handle:
                        browser_qa_evidence = json.load(handle)
                    if browser_qa_evidence.get("status") != "PASS":
                        raise ValueError("Browser QA evidence is not PASS")
                else:
                    browser_qa_evidence = {"status": "NOT_REQUIRED"}

                if requires_preview_invalid_credential_verification(task.description):
                    if not preview_required or not ui_required:
                        raise ValueError("Preview credential verification requires preview and UI validation")
                    with open(os.path.join(audit.report_dir, "browser_qa_scenario.json"), "r", encoding="utf-8") as handle:
                        browser_qa_scenario = json.load(handle)
                    if not has_preview_invalid_credential_evidence(browser_qa_scenario, browser_qa_evidence):
                        raise ValueError("Preview invalid-credential evidence is incomplete")
                manual_acceptance = None
                if state.manual_preview_acceptance_required:
                    manual_acceptance_ok, manual_acceptance = has_manual_preview_acceptance_evidence(audit.report_dir)
                    if not manual_acceptance_ok:
                        raise ValueError("Complete user manual Preview acceptance evidence is required")
                source_diff = collect_verified_source_diff(actual_changes)
                audit.save_json("final_review_source_evidence.json", {
                    "verified_changed_files": actual_changes,
                    "source_diff": source_diff,
                })
            except Exception as exc:
                state.state = TaskState.FAILED_STALLED
                state.reason = f"Final review evidence is incomplete: {exc}"
                break
            prompt = (
                "Perform a final evidence-based review without executing pytest, unittest, build, shell, "
                "PowerShell, bash, or any validation command in this read-only reviewer sandbox. Harness "
                "VALIDATING is the sole authority for product-test execution. Do not assume PASS. Return PASS only if the "
                "implementation result, verified repository changes, required validations, and prior review "
                "evidence all support completion.\n"
                f"Senior plan: {json.dumps(to_dict(senior_plan), ensure_ascii=False)}\n"
                f"Implementation result: {json.dumps(to_dict(implementation_result), ensure_ascii=False)}\n"
                f"Verified changed files: {json.dumps(actual_changes, ensure_ascii=False)}\n"
                f"Validation result: {json.dumps(to_dict(validation_result), ensure_ascii=False)}\n"
                f"Prior review: {json.dumps(to_dict(review_result), ensure_ascii=False)}\n"
                f"Preview evidence: {json.dumps(preview_evidence, ensure_ascii=False)}\n"
                f"Browser QA evidence: {json.dumps(browser_qa_evidence, ensure_ascii=False)}\n"
                f"Verified implementation source diff: {source_diff}\n"
                f"User manual Preview acceptance evidence: {json.dumps(manual_acceptance, ensure_ascii=False)}\n"
                "Task-specific validation amendment: the user explicitly prohibited authenticated or mutating Preview "
                "interactions against the shared data path. Do not require a direct Preview form save, forced error, "
                "or duplicate-save attempt as final evidence. Instead, verify server-side duplicate/error behavior from "
                "the passed Harness backend regression evidence and verify the frontend's displayed error/idempotency "
                "handling from the supplied implementation/review evidence. Return REVISE if that evidence is absent or "
                "contradictory; do not treat this amendment as permission to skip required tests or code review."
            )
            final_review_cmd = codex.build_review_command(prompt)
            final_review_raw = runner.run(final_review_cmd)
            audit.save_json("final_review_cli_result.json", {
                "exit_code": final_review_raw["exit_code"],
                "timed_out": final_review_raw["timed_out"],
                "stderr": final_review_raw["stderr"],
                "stdout": final_review_raw["stdout"],
            })
            terminal_state, reason = subprocess_gate(final_review_raw["exit_code"], "Final review")
            if terminal_state is not None:
                state.state = terminal_state
                state.reason = reason
                break
            try:
                fr = ReviewResult(**json.loads(final_review_raw["stdout"]))
                audit.save_json("final_review_result.json", to_dict(fr))
                if fr.status == ReviewStatus.PASS and commit_gate(senior_plan, implementation_result, actual_changes, validation_result, fr):
                    state.state = TaskState.READY_TO_COMMIT
                elif fr.status == ReviewStatus.REVISE:
                    if state.iteration >= MAX_AUTONOMOUS_REVIEW_ITERATIONS:
                        state.state = TaskState.FAILED_STALLED
                        state.reason = "Final Review requested changes after the autonomous revision limit"
                    else:
                        state.iteration += 1
                        state.state = TaskState.IMPLEMENTING
                        state.reason = "Final Review requested a scoped implementation revision"
                elif fr.status == ReviewStatus.NEED_USER_DECISION:
                    state.state = TaskState.NEED_USER_DECISION
                    state.reason = fr.summary or "Final reviewer requires a user decision"
                    notify_terminal_block(task_id, project_id, "FINAL_REVIEW_USER_DECISION_REQUIRED", state.reason, NotificationSeverity.ACTION_REQUIRED)
                else:
                    state.state = TaskState.FAILED_STALLED
                    state.reason = fr.summary or "Final review or commit gate did not pass"
            except Exception as e:
                print(f"Final Review Parsing failed: {str(e)}")
                state.state = TaskState.FAILED_STALLED
                state.reason = "Final review output failed ReviewResult schema parsing"
                
            state.last_successful_stage = TaskState.FINAL_REVIEW
            
        elif state.state == TaskState.READY_TO_COMMIT:
            approval_id = approval_mgr.request_approval(task_id, ApprovalAction.COMMIT.value, "Final Review Passed")
            print(f"Requested COMMIT approval: {approval_id}")
            state.blocking_approval_id = approval_id
            state.blocking_approval_action = ApprovalAction.COMMIT.value
            state.resume_stage = TaskState.COMMITTING
            state.state = TaskState.WAITING_FOR_USER_APPROVAL
            runtime.save_state(state)
            break
            
        elif state.state == TaskState.COMMITTING:
            if HARNESS_MODE == "H2_SYNTHETIC_E2E":
                state.state = TaskState.FAILED_STALLED
                state.reason = "Synthetic mode forbids commit and push"
                runtime.save_state(state)
                break
            from automation.git_executor import SafeGitExecutor
            git = SafeGitExecutor(PROJECT_ROOT)
            try:
                sha = git.commit(state.allowed_mutation_paths, f"Auto-commit for task {task_id}")
                state.commit_sha = sha
                approval_id = approval_mgr.request_approval(task_id, ApprovalAction.PUSH.value, "Commit successful, request push")
                print(f"Requested PUSH approval: {approval_id}")
                state.blocking_approval_id = approval_id
                state.blocking_approval_action = ApprovalAction.PUSH.value
                state.resume_stage = TaskState.PUSHING
                state.state = TaskState.WAITING_FOR_USER_APPROVAL
            except Exception as e:
                print(f"Commit failed: {e}")
                state.state = TaskState.FAILED_STALLED
            runtime.save_state(state)
            break
            
        elif state.state == TaskState.PUSHING:
            if HARNESS_MODE == "H2_SYNTHETIC_E2E":
                state.state = TaskState.FAILED_STALLED
                state.reason = "Synthetic mode forbids commit and push"
                runtime.save_state(state)
                break
            from automation.git_executor import SafeGitExecutor
            git = SafeGitExecutor(PROJECT_ROOT)
            try:
                push_evidence = execute_approved_push(approval_mgr, state, git)
                audit.save_json("push_result.json", push_evidence)
                state.state = TaskState.PUSHED
                state.last_successful_stage = TaskState.PUSHING
                state.state = TaskState.COMPLETED
            except Exception as exc:
                audit.save_json("push_result.json", {"status": "FAILED", "reason": str(exc)})
                state.state = TaskState.FAILED_STALLED
                state.reason = "Approved Git push failed; remote state was not assumed"
            runtime.save_state(state)
            break
            
        runtime.save_state(state)

    # Failure branches exit the loop with `break`; persist their terminal
    # state before returning so the supervisor does not misclassify them as a
    # crashed active worker.
    runtime.save_state(state)

    if state.state == TaskState.COMPLETED:
        permission_manager.restore_permissions()
        audit.log_event("TASK_COMPLETED", {"task_id": task_id})
        print(f"Task {task_id} completed successfully.")

if __name__ == "__main__":
    main()
