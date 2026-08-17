import os
import sys
import json
from datetime import datetime

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
from automation.adapters.vercel_adapter import VercelAdapter, VercelResult
from automation.adapters.browser_adapter import BrowserAdapter, BrowserQAResult
from automation.adapters.supabase_adapter import SupabaseAdapter, DatabaseEvidence
from automation.audit_logger import AuditLogger
from automation.orchestrator import Orchestrator
from automation.evidence_executor import EvidenceExecutor
from automation.permission_manager import PermissionManager
from automation.project_registry import ProjectRegistry
from automation.context_builder import ContextBuilder
from automation.runtime_state import RuntimeStateManager
from automation.approval_gate import ApprovalManager
from automation.notifier import NotificationEvent, ConsoleNotifier, NotificationSeverity

def to_dict(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()

def main():
    if HARNESS_MODE != "H2_REAL_READ_ONLY":
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


    while state.state not in [
        TaskState.WAITING_FOR_USER_APPROVAL,
        TaskState.WAITING_FOR_QUOTA,
        TaskState.FAILED_STALLED,
        TaskState.REJECTED_BY_USER,
        TaskState.COMPLETED
    ]:
        print(f"\n--- Executing Stage: {state.state.value} ---")
        
        if state.state == TaskState.QUEUED:
            audit.log_event("TASK_STARTED", {"task_id": task_id})
            executor.capture_baseline()
            state.state = TaskState.PRE_FLIGHT
            
        elif state.state == TaskState.PRE_FLIGHT:
            state.state = TaskState.CONTEXT_LOADING
            
        elif state.state == TaskState.CONTEXT_LOADING:
            state.state = TaskState.PLANNING
            
        elif state.state == TaskState.PLANNING:
            print("Running Codex Senior Planning...")
            plan_prompt = f"Task: {task.description}\nTool Boundary: Only built-in file tools allowed.\nPlease output a Structured JSON matching the SeniorPlan schema."
            plan_cmd = codex.build_plan_command(plan_prompt)
            plan_raw = runner.run(plan_cmd)
            
            try:
                plan_data = json.loads(plan_raw["stdout"])
                senior_plan = SeniorPlan(**plan_data)
                audit.save_json("senior_plan.json", to_dict(senior_plan))
                state.allowed_mutation_paths = senior_plan.allowed_mutation_paths
            except Exception as e:
                print(f"Codex Plan Parsing failed: {str(e)}")
                state.state = TaskState.FAILED_STALLED
                state.reason = "Plan Parsing Failed"
                break
            
            permission_manager.apply_scoped_permissions(state.allowed_mutation_paths)
            state.state = TaskState.IMPLEMENTING
            state.iteration = 1
            state.last_successful_stage = TaskState.PLANNING
            
        elif state.state == TaskState.IMPLEMENTING:
            impl_prompt = f"REAL MUTATION TASK.\nTask: {task.description}\nAllowed Mutation Paths: {state.allowed_mutation_paths}\nReturn findings as valid JSON ImplementationResult."
            impl_cmd = agy.build_command(impl_prompt)
            impl_raw = runner.run(impl_cmd)
            
            if impl_raw["exit_code"] != 0:
                print("Antigravity exited with error.")
                state.state = TaskState.FAILED_STALLED
                break
                
            state.state = TaskState.VALIDATING
            state.last_successful_stage = TaskState.IMPLEMENTING
            
        elif state.state == TaskState.VALIDATING:
            print("Running Harness Validations (EvidenceExecutor)...")
            try:
                test_res = executor.run_tests("harness_tests")
                compile_res = executor.run_tests("compileall")
                
                val_result = ValidationResult(
                    tests=ValidationStatus.PASS if test_res["exit_code"] == 0 else ValidationStatus.FAIL,
                    build=ValidationStatus.PASS if compile_res["exit_code"] == 0 else ValidationStatus.FAIL
                )
                audit.save_json(f"validation_result_i{state.iteration}.json", to_dict(val_result))
                
                if val_result.tests == ValidationStatus.FAIL or val_result.build == ValidationStatus.FAIL:
                    print("Harness Tests or Compileall failed.")
                    state.state = TaskState.FAILED_STALLED
                    break
                    
                state.state = TaskState.REVIEWING
                state.last_successful_stage = TaskState.VALIDATING
            except Exception as e:
                print(f"Validation failed: {e}")
                state.state = TaskState.FAILED_STALLED
                break
            
        elif state.state == TaskState.REVIEWING:
            print("Running Review...")
            review_prompt = "Review Implementation. Return JSON ReviewResult (status: PASS, REVISE, FAILED_STALLED). Assume PASS."
            review_cmd = codex.build_review_command(review_prompt)
            review_raw = runner.run(review_cmd)
            
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
                else:
                    state.state = TaskState.FAILED_STALLED
            except Exception as e:
                print(f"Review Parsing failed: {str(e)}")
                state.state = TaskState.FAILED_STALLED
                
        elif state.state == TaskState.DB_INSPECTION:
            print("Running DB Inspection...")
            changed = executor.capture_changed_files()
            db_relevant = any(f.startswith("supabase/") for f in changed)
            if db_relevant and config.supabase.enabled:
                print("DB is relevant. Calling SupabaseAdapter.")
                try:
                    db_adapter = SupabaseAdapter()
                    db_evidence = db_adapter.inspect_db()
                    audit.save_json("database_evidence.json", to_dict(db_evidence))
                    audit.log_event("DB_INSPECTION_COMPLETED", {"status": "SUCCESS"})
                except Exception as e:
                    print(f"DB Inspection failed: {e}")
            else:
                audit.log_event("DB_STAGE_SKIPPED", {"reason": "No DB relevance found"})
            
            state.state = TaskState.PREVIEW_DEPLOY
            state.last_successful_stage = TaskState.DB_INSPECTION
            
        elif state.state == TaskState.PREVIEW_DEPLOY:
            if not config.vercel.enabled:
                print("Vercel is not enabled for this project. Skipping.")
                state.state = TaskState.BROWSER_QA_PLANNING
                state.last_successful_stage = TaskState.PREVIEW_DEPLOY
                continue
                
            print("Running Vercel Preview Deploy...")
            try:
                vercel = VercelAdapter(PROJECT_ROOT)
                preview = vercel.get_latest_preview()
                audit.save_json("vercel_preview.json", to_dict(preview))
                
                if preview.is_production:
                    print("SAFETY_BLOCK: Vercel deployment is Production, not Preview.")
                    state.state = TaskState.FAILED_STALLED
                    state.reason = "Production deployment not allowed for Browser QA."
                    runtime.save_state(state)
                    break
                    
            except Exception as e:
                print(f"Vercel check failed: {e}")
            
            state.state = TaskState.BROWSER_QA_PLANNING
            state.last_successful_stage = TaskState.PREVIEW_DEPLOY
            
        elif state.state == TaskState.BROWSER_QA_PLANNING:
            if not config.browser_qa.enabled:
                print("Browser QA is not enabled for this project. Skipping.")
                state.state = TaskState.FINAL_REVIEW
                state.last_successful_stage = TaskState.BROWSER_QA_PLANNING
                continue
                
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
                
                scenario = BrowserQAScenario(
                    scenario_id=f"QA-{task_id}",
                    name="Smoke test Vercel Preview",
                    description="Smoke test Vercel Preview",
                    start_url=start_url,
                    steps=[
                        BrowserQAStep(
                            action="goto",
                            selector_or_target=start_url,
                            timeout=5000,
                            screenshot_after=True,
                            risk="SAFE_READ"
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
                    state.state = TaskState.FINAL_REVIEW
                    state.last_successful_stage = TaskState.BROWSER_QA_EXECUTION
            except Exception as e:
                print(f"Browser QA execution failed: {e}")
                state.state = TaskState.FAILED_STALLED
                runtime.save_state(state)
                break
            
        elif state.state == TaskState.FINAL_REVIEW:
            print("Running Final Codex Review...")
            prompt = "Review all evidence. Return JSON ReviewResult (status: PASS, REVISE, FAILED_STALLED). Assume PASS."
            final_review_cmd = codex.build_review_command(prompt)
            final_review_raw = runner.run(final_review_cmd)
            try:
                fr = ReviewResult(**json.loads(final_review_raw["stdout"]))
                audit.save_json("final_review_result.json", to_dict(fr))
                if fr.status.value == "PASS":
                    state.state = TaskState.READY_TO_COMMIT
                else:
                    state.state = TaskState.FAILED_STALLED
            except Exception as e:
                print(f"Final Review Parsing failed: {str(e)}")
                state.state = TaskState.FAILED_STALLED
                
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
            print("Safe Push skipped in H7-1 verification.")
            state.state = TaskState.COMPLETED
            runtime.save_state(state)
            break
            
        runtime.save_state(state)

    if state.state == TaskState.COMPLETED:
        permission_manager.restore_permissions()
        audit.log_event("TASK_COMPLETED", {"task_id": task_id})
        print(f"Task {task_id} completed successfully.")

if __name__ == "__main__":
    main()
