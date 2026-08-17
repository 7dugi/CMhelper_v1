import argparse
import sys
from pathlib import Path
from .approval_gate import ApprovalManager, ApprovalStatus
from .runtime_state import RuntimeStateManager
from .models import TaskState

def get_parser():
    parser = argparse.ArgumentParser(description="CMhelper Control CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    status_p = subparsers.add_parser("status", help="Get task status")
    status_p.add_argument("task_id", help="Task ID")
    
    approve_p = subparsers.add_parser("approve", help="Approve a pending action")
    approve_p.add_argument("task_id", help="Task ID")
    
    reject_p = subparsers.add_parser("reject", help="Reject a pending action")
    reject_p.add_argument("task_id", help="Task ID")

    pause_p = subparsers.add_parser("pause", help="Pause a task")
    pause_p.add_argument("task_id", help="Task ID")

    resume_p = subparsers.add_parser("resume", help="Resume a paused task")
    resume_p.add_argument("task_id", help="Task ID")
    
    return parser

def main():
    parser = get_parser()
    args = parser.parse_args()
    
    root_dir = str(Path(__file__).parent.parent)
    approval_mgr = ApprovalManager(root_dir)
    runtime_mgr = RuntimeStateManager(root_dir)
    
    if args.command == "status":
        state = runtime_mgr.load_state()
        app_status = approval_mgr.check_status(args.task_id)
        if state and state.task_id == args.task_id:
            print(f"Task: {state.task_id}")
            print(f"State: {state.state.value}")
            print(f"Provider: {state.provider}")
            print(f"Last successful stage: {state.last_successful_stage.value if state.last_successful_stage else 'None'}")
            print(f"Approval status: {app_status.value if app_status else 'None'}")
        else:
            print(f"Task {args.task_id} runtime state not found (or another task is active).")
            if app_status:
                print(f"Approval status: {app_status.value}")
            
    elif args.command == "approve":
        state = runtime_mgr.load_state()
        if not state or state.task_id != args.task_id:
            print("Cannot approve: task is not the active runtime state.")
            sys.exit(1)
            
        success = approval_mgr.decide(args.task_id, approved=True)
        if success:
            print(f"Task {args.task_id} approved.")
            if state.state == TaskState.WAITING_FOR_USER_APPROVAL:
                state.state = TaskState.APPROVED_TO_COMMIT
                runtime_mgr.save_state(state)
                print("Task state updated to APPROVED_TO_COMMIT.")
        else:
            print(f"Failed to approve task {args.task_id}. Make sure it is PENDING.")
            
    elif args.command == "reject":
        state = runtime_mgr.load_state()
        if not state or state.task_id != args.task_id:
            print("Cannot reject: task is not the active runtime state.")
            sys.exit(1)
            
        success = approval_mgr.decide(args.task_id, approved=False)
        if success:
            print(f"Task {args.task_id} rejected.")
            if state.state == TaskState.WAITING_FOR_USER_APPROVAL:
                state.state = TaskState.REJECTED_BY_USER
                runtime_mgr.save_state(state)
                print("Task state updated to REJECTED_BY_USER.")
        else:
            print(f"Failed to reject task {args.task_id}. Make sure it is PENDING.")

    elif args.command == "pause":
        state = runtime_mgr.load_state()
        if state and state.task_id == args.task_id:
            if state.state not in [TaskState.COMPLETED, TaskState.FAILED, TaskState.PAUSED]:
                state.state = TaskState.PAUSED
                runtime_mgr.save_state(state)
                print(f"Task {args.task_id} PAUSED.")
            else:
                print(f"Task {args.task_id} cannot be paused from state {state.state.value}.")
        else:
            print("Task not found.")

    elif args.command == "resume":
        state = runtime_mgr.load_state()
        if state and state.task_id == args.task_id:
            if state.state == TaskState.PAUSED:
                state.state = TaskState.RESUMING
                runtime_mgr.save_state(state)
                print(f"Task {args.task_id} marked for RESUMING.")
            else:
                print(f"Task {args.task_id} is not PAUSED.")
        else:
            print("Task not found.")

if __name__ == "__main__":
    main()
