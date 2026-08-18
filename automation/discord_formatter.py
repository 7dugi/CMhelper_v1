def build_enhanced_approval_message(task_state, approval_id: str, action: str, reason: str) -> str:
    action_desc = "작업을 승인하기 위한 권한이 필요합니다."
    if_approved = "승인된 작업이 실행됩니다."
    if_rejected = "작업이 중단됩니다."
    risk = "UNKNOWN"
    
    if action == "COMMIT":
        action_desc = "검증이 완료된 변경사항을 로컬 Git Commit으로 확정하기 위한 승인이 필요합니다."
        if_approved = "현재 승인 대상 파일만 Git Commit합니다. 원격 GitHub Push는 수행하지 않습니다."
        if_rejected = "Commit하지 않고 Task를 중단하거나 수정 단계로 돌립니다."
        risk = "LOW"
    elif action == "PUSH":
        action_desc = "로컬 Commit을 원격 GitHub Branch에 업로드하기 위한 승인이 필요합니다."
        if_approved = "현재 Commit을 지정된 Remote Branch로 Push합니다."
        if_rejected = "Local Commit은 유지하고 Push하지 않습니다."
        risk = "MEDIUM"
    elif action == "DATABASE_WRITE":
        action_desc = "데이터베이스 변경은 실제 데이터에 영향을 줄 수 있어 사용자 승인이 필요합니다."
        if_approved = "지정된 데이터베이스 쿼리를 실행하거나 마이그레이션을 적용합니다."
        if_rejected = "데이터베이스를 변경하지 않고 작업을 중단합니다."
        risk = "HIGH"
    elif action == "PRODUCTION_DEPLOY":
        action_desc = "변경사항을 Production 환경에 반영하기 위한 승인이 필요합니다."
        if_approved = "검증된 Commit을 Production 환경에 배포합니다."
        if_rejected = "Production 배포를 취소하고 중단합니다."
        risk = "HIGH"

    title = task_state.task_title or "Unknown Task" if task_state else "Unknown Task"
    
    work_completed = task_state.task_description or "" if task_state else ""
    lines = work_completed.strip().split("\n")
    if len(lines) > 3:
        work_completed = "\n".join(lines[:3]) + "\n... (truncated)"
        
    changed_files = task_state.allowed_mutation_paths or [] if task_state else []
    if len(changed_files) == 0:
        changes_str = "None or UNKNOWN"
    else:
        num_changes = len(changed_files)
        file_list = "\n".join([f"- {f}" for f in changed_files[:5]])
        if num_changes > 5:
            file_list += f"\n  + {num_changes - 5} more files"
        changes_str = f"{num_changes} files changed\n{file_list}"
        
    tests_status = "UNKNOWN"
    browser_status = "UNKNOWN"
    final_review_status = "UNKNOWN"
    
    if task_state and hasattr(task_state, "last_successful_stage"):
        ls = task_state.last_successful_stage
        if ls in ["VALIDATING", "REVIEWING", "DB_INSPECTION", "PREVIEW_DEPLOY", "BROWSER_QA_EXECUTION", "FINAL_REVIEW"]:
            tests_status = "PASS"
        if ls == "FINAL_REVIEW":
            final_review_status = "PASS"
            browser_status = "PASS / SKIPPED"
        if ls == "BROWSER_QA_EXECUTION":
            browser_status = "PASS / SKIPPED"

    project_id = task_state.project_id if task_state and task_state.project_id else "UNKNOWN"
    task_id = task_state.task_id if task_state else "UNKNOWN"
    state_str = task_state.state if task_state else "WAITING_FOR_USER_APPROVAL"

    msg = f"""
[ACTION REQUIRED]

Project:
{project_id}

Task:
{title}

Task ID:
{task_id}

Approval:
{approval_id}

Requested Action:
{action}

Why approval is needed:
{action_desc}

Work completed:
{work_completed}

Changes:
{changes_str}

Validation:
Tests: {tests_status}
Browser QA: {browser_status}
Final Review: {final_review_status}

Risk:
{risk}

If approved:
{if_approved}

If rejected:
{if_rejected}

Current state:
{state_str}
"""
    return msg.strip()
