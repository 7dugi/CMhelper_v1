import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import subprocess

from .config import SUPERVISOR_POLL_SECONDS, QUOTA_PROBE_INTERVALS_MINUTES, QUOTA_PROBE_MAX_INTERVAL_MINUTES
from .runtime_state import RuntimeStateManager, RuntimeTaskState
from .task_lock import TaskLockManager
from .quota_probe import ProviderHealthChecker
from .provider_status import ProviderStatus
from .models import TaskState
from .notifier import NotificationEvent, NotificationSeverity, dispatch_notification
from .approval_gate import ApprovalManager, ApprovalStatus
from .health_check import ProviderHealthChecker as NewProviderHealthChecker

class Supervisor:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.runtime_mgr = RuntimeStateManager(root_dir)
        self.lock_mgr = TaskLockManager(root_dir)
        self.probe = ProviderHealthChecker()
        self.health_checker = NewProviderHealthChecker(root_dir)

    def _run_worker(self, task_state: RuntimeTaskState):
        env = os.environ.copy()
        env["HARNESS_TASK_ID"] = task_state.task_id
        env["HARNESS_PROJECT_ID"] = getattr(task_state, "project_id", "cmhelper")
        env["PYTHONPATH"] = self.root_dir
        subprocess.run([sys.executable, "-m", "automation.main"], env=env, cwd=self.root_dir)

    def _handle_crash_recovery(self, state: RuntimeTaskState):
        if state.state in [TaskState.IMPLEMENTING, TaskState.REVIEWING, TaskState.PLANNING, TaskState.DESIGNING, TaskState.VALIDATING, TaskState.COMMITTING, TaskState.PUSHING]:
            if not self.lock_mgr.is_locked():
                # Process crashed
                dispatch_notification(NotificationEvent(
                    event_type="CRASH_DETECTED",
                    message=f"Task {state.task_id} was left in {state.state.value} without active lock.",
                    task_id=state.task_id,
                    project_id=state.project_id,
                    severity=NotificationSeverity.ERROR
                ))
                
                # Crash recovery policy
                if state.last_successful_stage and state.resume_stage:
                    state.state = TaskState.RESUMING
                    self.runtime_mgr.save_state(state)
                    dispatch_notification(NotificationEvent(
                        event_type="RECOVERED",
                        message=f"Task {state.task_id} will be resumed from {state.resume_stage.value}.",
                        task_id=state.task_id,
                        project_id=state.project_id,
                        send_to_discord=True
                    ))
                else:
                    state.state = TaskState.NEED_USER_DECISION
                    self.runtime_mgr.save_state(state)
                    dispatch_notification(NotificationEvent(
                        event_type="MANUAL_INTERVENTION_REQUIRED",
                        message=f"Task {state.task_id} cannot be automatically recovered. Manual intervention is required.",
                        task_id=state.task_id,
                        project_id=state.project_id,
                        severity=NotificationSeverity.ACTION_REQUIRED,
                        send_to_discord=True
                    ))

    def _handle_quota_wait(self, state: RuntimeTaskState, now: datetime):
        if self.runtime_mgr.can_resume(now):
            dispatch_notification(NotificationEvent(
                event_type="QUOTA_PROBE",
                message=f"Probing {state.provider} for quota availability.",
                task_id=state.task_id,
                project_id=state.project_id
            ))
            
            ev = self.probe.check(state.provider)
            if ev.status == ProviderStatus.AVAILABLE:
                state.state = TaskState.RESUMING
                state.quota_probe_attempts = 0
                state.next_probe_at = None
                self.runtime_mgr.save_state(state)
                dispatch_notification(NotificationEvent(
                    event_type="QUOTA_AVAILABLE",
                    message=f"Quota available for {state.provider}. Resuming.",
                    task_id=state.task_id,
                    project_id=state.project_id,
                    send_to_discord=True
                ))
                return True # Request run
            else:
                state.quota_probe_attempts += 1
                idx = min(state.quota_probe_attempts - 1, len(QUOTA_PROBE_INTERVALS_MINUTES) - 1)
                wait_min = QUOTA_PROBE_INTERVALS_MINUTES[idx] if idx >= 0 else QUOTA_PROBE_MAX_INTERVAL_MINUTES
                wait_min = min(wait_min, QUOTA_PROBE_MAX_INTERVAL_MINUTES)
                
                state.next_probe_at = now + timedelta(minutes=wait_min)
                self.runtime_mgr.save_state(state)
                dispatch_notification(NotificationEvent(
                    event_type="QUOTA_STILL_EXHAUSTED",
                    message=f"Quota probe failed. Next probe at {state.next_probe_at.isoformat()}.",
                    task_id=state.task_id
                ))
        return False

    def loop_once(self):
        state = self.runtime_mgr.load_state()
        if not state or state.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.REJECTED_BY_USER]:
            new_state = self.runtime_mgr.dequeue_task()
            if new_state:
                dispatch_notification(NotificationEvent(
                    event_type="TASK_DEQUEUED",
                    message=f"Dequeued task {new_state.task_id} ('{new_state.task_title}').",
                    task_id=new_state.task_id,
                    project_id=new_state.project_id
                ))
                state = new_state
            else:
                return
        
        now = datetime.now(timezone.utc)
        
        # Check for crashes
        self._handle_crash_recovery(state)
        
        state = self.runtime_mgr.load_state()
        if not state:
            return
            
        if state.state == TaskState.QUEUED:
            if not self.lock_mgr.is_locked():
                dispatch_notification(NotificationEvent(
                    event_type="TASK_STARTING",
                    message=f"Starting queued task {state.task_id}.",
                    task_id=state.task_id,
                    project_id=state.project_id,
                    send_to_discord=True
                ))
                self._run_worker(state)

        elif state.state == TaskState.WAITING_FOR_QUOTA:
            if not self.lock_mgr.is_locked():
                if self._handle_quota_wait(state, now):
                    self._run_worker(state)
                    
        elif state.state == TaskState.WAITING_FOR_USER_APPROVAL:
            if not self.lock_mgr.is_locked():
                app_mgr = ApprovalManager(self.root_dir)
                if state.blocking_approval_id:
                    app = app_mgr.get_approval(state.blocking_approval_id)
                    if app:
                        if app.status == ApprovalStatus.APPROVED:
                            state.state = state.resume_stage or TaskState.RESUMING
                            self.runtime_mgr.save_state(state)
                            
                            dispatch_notification(NotificationEvent(
                                event_type="APPROVAL_GRANTED",
                                message=f"Approval {app.approval_id} granted. Resuming from {state.state.value}.",
                                task_id=state.task_id,
                                project_id=state.project_id,
                                send_to_discord=True
                            ))
                            self._run_worker(state)
                        elif app.status == ApprovalStatus.REJECTED:
                            state.state = TaskState.REJECTED_BY_USER
                            self.runtime_mgr.save_state(state)
                        elif app.status == ApprovalStatus.EXPIRED:
                            state.state = TaskState.NEED_USER_DECISION
                            self.runtime_mgr.save_state(state)
                
        elif state.state == TaskState.RESUMING:
            if not self.lock_mgr.is_locked():
                self._run_worker(state)

    def run(self):
        from .task_lock import SupervisorLockManager
        sup_lock = SupervisorLockManager(self.root_dir)
        if not sup_lock.acquire():
            print("ALREADY_RUNNING")
            sys.exit(0)
            
        print("Supervisor started. Checking provider health...")
        self.health_checker.check_all()
        
        # Start Discord Bot
        bot_process = None
        if os.environ.get("DISCORD_BOT_TOKEN"):
            print("Starting Discord Approval Bot...")
            bot_process = subprocess.Popen([sys.executable, "-m", "automation.discord_bot"], cwd=self.root_dir)
        
        try:
            while True:
                try:
                    self.loop_once()
                    time.sleep(SUPERVISOR_POLL_SECONDS)
                except KeyboardInterrupt:
                    print("Supervisor stopped.")
                    break
                except Exception as e:
                    print(f"Supervisor error: {e}")
                    time.sleep(SUPERVISOR_POLL_SECONDS)
        finally:
            if bot_process:
                bot_process.terminate()
            sup_lock.release()

if __name__ == "__main__":
    root = str(Path(__file__).parent.parent)
    sup = Supervisor(root)
    sup.run()
