import json
import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from .models import TaskState

class RuntimeTaskState(BaseModel):
    task_id: str
    state: TaskState
    provider: str = ""
    reason: str = ""
    detected_at: Optional[datetime] = None
    suggested_resume_at: Optional[datetime] = None
    resume_stage: Optional[TaskState] = None
    iteration: int = 1
    allowed_mutation_paths: List[str] = Field(default_factory=list)
    last_successful_stage: Optional[TaskState] = None
    quota_probe_attempts: int = 0
    next_probe_at: Optional[datetime] = None
    commit_sha: Optional[str] = None
    push_policy: str = "APPROVE_COMMIT_ONLY" # default to mock/no push

class RuntimeStateManager:
    def __init__(self, root_dir: str):
        self.runtime_dir = Path(root_dir) / "automation" / "runtime"
        self.state_file = self.runtime_dir / "task_state.json"
        
        # Ensure runtime dir exists
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, state: RuntimeTaskState):
        temp_file = self.state_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(state.model_dump_json(indent=2))
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(self.state_file)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e

    def load_state(self) -> Optional[RuntimeTaskState]:
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return RuntimeTaskState(**data)
        except Exception as e:
            print(f"Failed to load runtime state: {e}")
            return None

    def clear_state(self):
        if self.state_file.exists():
            self.state_file.unlink()

    def can_resume(self, now: datetime = None) -> bool:
        state = self.load_state()
        if not state:
            return False
            
        if state.state not in [TaskState.WAITING_FOR_QUOTA, TaskState.WAITING_FOR_USER_APPROVAL, TaskState.FAILED_STALLED, TaskState.PAUSED]:
            # It's in an active state. Crash recovery will decide.
            if state.resume_stage:
                return True
            return False

        if state.state == TaskState.WAITING_FOR_QUOTA:
            # Check suggested_resume_at
            current_time = now or datetime.now(timezone.utc)
            if state.suggested_resume_at:
                if current_time < state.suggested_resume_at:
                    return False # Too early to resume
                return True
            
            # If no suggested time, check backoff probe time
            if state.next_probe_at:
                if current_time < state.next_probe_at:
                    return False
                return True
                
            return True
            
        if state.state == TaskState.WAITING_FOR_USER_APPROVAL:
            # Need explicit user input to resume
            return False
            
        if state.state == TaskState.PAUSED:
            return False

        return False
