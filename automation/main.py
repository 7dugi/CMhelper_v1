import os
import sys
import json
import subprocess
import time
from datetime import datetime

# Set up utf-8 encoding for stdout/stderr to prevent cp949 crash on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from automation.config import PROJECT_ROOT, HARNESS_MODE
from automation.models import Task, TaskState, RiskLevel, TaskContext, SeniorPlan, ImplementationResult, ReviewResult, ValidationResult, ReviewStatus, ValidationStatus
from automation.governance import GovernanceLoader
from automation.cli_runner import CLIRunner
from automation.adapters.codex_adapter import CodexAdapter
from automation.adapters.antigravity_adapter import AntigravityAdapter
from automation.audit_logger import AuditLogger
from automation.orchestrator import Orchestrator
from automation.evidence_executor import EvidenceExecutor

def main():
    if HARNESS_MODE != "H2_REAL_READ_ONLY":
        print("Error: This E2E test requires HARNESS_MODE='H2_REAL_READ_ONLY'")
        sys.exit(1)

    task_id = "H2-REAL-E2E-006"
    audit = AuditLogger(task_id)
    runner = CLIRunner()
    executor = EvidenceExecutor()

    # Verify executables
    codex_path, codex_src = runner.resolve_executable("codex")
    agy_path, agy_src = runner.resolve_executable("agy")

    if "mock_bin" in str(codex_path) or "mock_bin" in str(agy_path):
        print("FAIL: Mock binary detected!")
        sys.exit(1)

    audit.log_event("CLI_RESOLUTION", {
        "codex_executable": str(codex_path),
        "antigravity_executable": str(agy_path),
        "codex_resolution_source": codex_src,
        "antigravity_resolution_source": agy_src,
        "mock_used": False
    })

    # 1. Preflight
    audit.log_event("TASK_STARTED", {"task_id": task_id, "mode": HARNESS_MODE})
    git_before = executor.capture_repo_snapshot()
    audit.save_text("git_before.json", json.dumps({"snapshot": git_before}))

    task = Task(
        id=task_id,
        title="Backend Domain Read-Only Analysis",
        description="""CMhelper Repository의 Governance 문서와 현재 Backend 코드를 실제로 읽고, 현재 Backend의 주요 Domain을 5개 이하로 정리하라. 각 Domain마다 실제 코드 또는 Governance에서 확인한 근거를 간단히 포함하라.

READ ONLY.
Antigravity Implementer CAN:
- trusted workspace 내부 파일 읽기
- directory/file 탐색을 위한 Antigravity built-in file tools 사용

Antigravity Implementer CANNOT:
- shell command, git command, rg/ripgrep, pytest, npm, MCP, Vercel 사용 금지
- 파일 수정 금지

*중요: required_validations 작성 시 shell command(예: git, rg, pytest, npm 등)를 절대 포함하지 마세요. 대신 'unit tests required', 'architecture verification required' 등 선언적(Declarative)으로 작성하세요.*""",
        state=TaskState.PRE_FLIGHT
    )

    # 2. Governance
    loader = GovernanceLoader()
    docs = loader.load_core_documents()
    
    expected_docs = [
        ".agents/AGENTS.md",
        "docs/PROJECT_OVERVIEW.md",
        "docs/CURRENT_STATUS.md",
        "docs/DEVELOPMENT_GATE.md",
        "docs/TECHNICAL_PRINCIPLES.md",
        "docs/ROADMAP.md",
        "docs/TODO.md",
        "docs/UI_INFORMATION_ARCHITECTURE.md"
    ]
    for d in expected_docs:
        found = False
        for k in docs.keys():
            if d.replace("/", os.sep) in str(k) or d in str(k):
                found = True
                break
        if not found:
            print(f"FAIL: Required governance document {d} not loaded.")
            sys.exit(1)

    context = TaskContext(
        task=task,
        repository_root=PROJECT_ROOT,
        branch="feature/dev-harness-v1",
        head="HEAD",
        loaded_documents=docs
    )
    
    def to_dict(model):
        return model.model_dump() if hasattr(model, "model_dump") else model.dict()

    audit.save_json("governance.json", {k: to_dict(v) for k, v in docs.items()})

    codex = CodexAdapter()
    agy = AntigravityAdapter()
    orchestrator = Orchestrator(context)
    orchestrator.load_context()

    print("Running Codex Senior Planning...")
    orchestrator.create_plan()
    
    # 3. Codex Planning
    plan_cmd = codex.build_plan_command(task.description)
    plan_raw = runner.run(plan_cmd)
    audit.save_text("senior_plan_raw.txt", f"STDOUT:\n{plan_raw['stdout']}\nSTDERR:\n{plan_raw['stderr']}")
    
    if plan_raw['exit_code'] != 0 or plan_raw.get('timed_out', False):
        print("Codex Planning failed.")
        sys.exit(1)

    try:
        plan_data = json.loads(plan_raw["stdout"])
        senior_plan = SeniorPlan(**plan_data)
        audit.save_json("senior_plan.json", to_dict(senior_plan))
        audit.log_event("CODEX_PLAN", to_dict(senior_plan))
    except Exception as e:
        print(f"Codex Plan Parsing failed: {str(e)}")
        sys.exit(1)
        
    # SeniorPlan Validation Check for false assumptions
    invalid_keywords = ["수단이 없어", "수단이 없음", "열람할 수", "접근 불가", "cannot read repository", "no file access", "impossible"]
    combined_text = senior_plan.summary + " " + " ".join(senior_plan.scope) + " " + " ".join(senior_plan.out_of_scope)
    for kw in invalid_keywords:
        if kw in combined_text:
            print(f"FAIL: SeniorPlan contains invalid assumption regarding file access: '{kw}'")
            sys.exit(1)

    print("Running Antigravity Implementer...")
    orchestrator.request_implementation()

    # 4. Antigravity Implementer
    impl_prompt = f"""READ ONLY ANALYSIS TASK.
SeniorPlan의 요구사항을 실제 Repository에서 검증하라.
허용:
- workspace 내부 파일 읽기 (built-in file tools)

절대 금지:
- shell command 실행 금지 (git, rg, pytest, npm 등)
- MCP 사용 금지
- 파일 수정/생성/삭제 금지
- Vercel 실행 금지
- Supabase write 금지

Project Root: {PROJECT_ROOT}
Task Objective: {task.description}
Senior Plan Summary: {senior_plan.summary}
Scope: {', '.join(senior_plan.scope)}
Acceptance Criteria: {json.dumps(to_dict(senior_plan).get('acceptance_criteria', []))}
Required Validations: {', '.join(senior_plan.required_validations)}

Execute the verification using ONLY read-only file methods. Do NOT attempt to run shell commands.
Return your findings strictly as valid JSON matching the ImplementationResult structure.
The structure requires these exact keys and types: (summary: string, changed_files: array of strings, tests: string, build: string, db_impact: string, ui_impact: string, issues: array of strings, user_decision_required: boolean)."""
    
    impl_cmd = agy.build_command(impl_prompt)
    impl_raw = runner.run(impl_cmd)
    audit.save_text("implementer_raw.txt", f"STDOUT:\n{impl_raw['stdout']}\nSTDERR:\n{impl_raw['stderr']}")
    
    if "auto-denied" in impl_raw['stderr']:
        print("FAIL: auto-denied detected. Antigravity attempted to use a forbidden tool.")
        sys.exit(1)
        
    if impl_raw['exit_code'] != 0 or impl_raw.get('timed_out', False):
        print(f"Antigravity Implementation failed. Exit: {impl_raw['exit_code']}")
        sys.exit(1)

    try:
        raw_out = impl_raw["stdout"].strip()
        if raw_out.startswith("```json"):
            raw_out = raw_out.split("```json")[1].split("```")[0].strip()
        elif "{" in raw_out:
            raw_out = raw_out[raw_out.find("{"):raw_out.rfind("}")+1]
        
        impl_data = json.loads(raw_out)
        impl_result = ImplementationResult(**impl_data)
        audit.save_json("implementation_result.json", to_dict(impl_result))
    except Exception as e:
        print(f"Antigravity Impl Parsing failed: {str(e)}")
        sys.exit(1)

    # 5. Harness Git Evidence After (Mutation Guard)
    git_after = executor.capture_repo_snapshot()
    audit.save_text("git_after.json", json.dumps({"snapshot": git_after}))
    
    if git_before.strip() != git_after.strip() or len(impl_result.changed_files) > 0:
        print("FAIL: Mutation Guard triggered. Unexpected mutation detected!")
        sys.exit(1)

    print("Running Codex Senior Review...")
    orchestrator.review_result()

    # 6. Codex Review
    review_prompt = f"""Review the ImplementationResult.
Original Task: {task.description}
Senior Plan Summary: {senior_plan.summary}

NOTE TO REVIEWER: Antigravity's built-in file read tools are perfectly normal and permitted. Shell command restriction does NOT mean repository file read restriction. If the implementer claims to have inspected files, it was done legally via native tools.

Implementation Result:
- Summary: {impl_result.summary}
- Changed Files: {impl_result.changed_files}
- Tests: {impl_result.tests}
- Build: {impl_result.build}
- DB Impact: {impl_result.db_impact}
- UI Impact: {impl_result.ui_impact}
- Issues: {impl_result.issues}

Mutation Guard: Harness confirmed NO Git mutation.
Evaluate if the implementer successfully executed the plan using read-only methods.
"""
    review_cmd = codex.build_review_command(review_prompt)
    review_raw = runner.run(review_cmd)
    audit.save_text("senior_review_raw.txt", f"STDOUT:\n{review_raw['stdout']}\nSTDERR:\n{review_raw['stderr']}")

    if review_raw['exit_code'] != 0 or review_raw.get('timed_out', False):
        print(f"Codex Review failed with code {review_raw['exit_code']}")
        sys.exit(1)

    try:
        review_data = json.loads(review_raw["stdout"])
        review_result = ReviewResult(**review_data)
        audit.save_json("review_result.json", to_dict(review_result))
        audit.log_event("CODEX_REVIEW", to_dict(review_result))
    except Exception as e:
        print(f"Codex Review Parsing failed: {str(e)}")
        sys.exit(1)

    # 7. PassGate check
    orchestrator.handle_review_result(review_result)
    if review_result.status != ReviewStatus.PASS:
        print(f"PassGate FAILED: ReviewStatus is {review_result.status}")
        sys.exit(1)
        
    validation_result = ValidationResult(
        tests=ValidationStatus.NOT_REQUIRED,
        build=ValidationStatus.NOT_REQUIRED,
        database=ValidationStatus.NOT_REQUIRED,
        preview=ValidationStatus.NOT_REQUIRED,
        ui=ValidationStatus.NOT_REQUIRED
    )
    audit.save_json("validation_result.json", to_dict(validation_result))

    final_report = f"""# H2-REAL-E2E-006 Complete
Status: {review_result.status.value}
State: {orchestrator.sm.current_state.value}
No mutations detected.
"""
    audit.save_text("final_report.md", final_report)
    print("E2E H2-REAL-E2E-006 Run Completed Successfully.")

if __name__ == "__main__":
    main()
