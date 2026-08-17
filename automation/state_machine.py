from typing import Dict, List, Optional
from .models import TaskState

TRANSITIONS: Dict[TaskState, List[TaskState]] = {
    TaskState.NEW: [TaskState.PRE_FLIGHT],
    TaskState.PRE_FLIGHT: [TaskState.CONTEXT_LOADING, TaskState.FAILED],
    TaskState.CONTEXT_LOADING: [TaskState.PLANNING, TaskState.NEED_USER_DECISION, TaskState.FAILED],
    TaskState.PLANNING: [TaskState.DESIGNING, TaskState.IMPLEMENTING, TaskState.NEED_USER_DECISION],
    TaskState.DESIGNING: [TaskState.IMPLEMENTING, TaskState.NEED_USER_DECISION],
    TaskState.IMPLEMENTING: [TaskState.REVIEWING, TaskState.FAILED],
    TaskState.REVIEWING: [TaskState.REVISING, TaskState.VALIDATING, TaskState.NEED_USER_DECISION, TaskState.FAILED_STALLED],
    TaskState.REVISING: [TaskState.IMPLEMENTING, TaskState.NEED_USER_DECISION, TaskState.FAILED_STALLED],
    TaskState.VALIDATING: [TaskState.TESTING, TaskState.BUILDING, TaskState.DB_VERIFY, TaskState.PREVIEW_DEPLOY, TaskState.UI_VERIFY, TaskState.READY_TO_COMMIT, TaskState.REVISING],
    TaskState.TESTING: [TaskState.VALIDATING],
    TaskState.BUILDING: [TaskState.VALIDATING],
    TaskState.DB_VERIFY: [TaskState.VALIDATING],
    TaskState.PREVIEW_DEPLOY: [TaskState.VALIDATING],
    TaskState.UI_VERIFY: [TaskState.VALIDATING],
    TaskState.NEED_USER_DECISION: [], # Resume explicitly handled
    TaskState.FAILED_STALLED: [],     # Resume explicitly handled
    TaskState.READY_TO_COMMIT: [TaskState.COMMITTING],
    TaskState.COMMITTING: [TaskState.COMPLETED, TaskState.FAILED],
    TaskState.COMPLETED: [],
    TaskState.FAILED: []
}

class StateMachine:
    def __init__(self, initial_state: TaskState = TaskState.NEW):
        self.current_state = initial_state
        self._pause_state: Optional[TaskState] = None

    def can_transition(self, next_state: TaskState) -> bool:
        if self.current_state in [TaskState.NEED_USER_DECISION, TaskState.FAILED_STALLED]:
            return next_state == self._pause_state if self._pause_state else False
        return next_state in TRANSITIONS.get(self.current_state, [])

    def transition(self, next_state: TaskState):
        if not self.can_transition(next_state):
            raise ValueError(f"Invalid state transition from {self.current_state} to {next_state}")
        
        if next_state in [TaskState.NEED_USER_DECISION, TaskState.FAILED_STALLED]:
            self._pause_state = self.current_state
        else:
            if self.current_state in [TaskState.NEED_USER_DECISION, TaskState.FAILED_STALLED]:
                self._pause_state = None
        
        self.current_state = next_state

    def resume_state(self):
        if self.current_state not in [TaskState.NEED_USER_DECISION, TaskState.FAILED_STALLED]:
            raise ValueError("Not in a paused state")
        if not self._pause_state:
            raise ValueError("No pause state recorded")
        self.current_state = self._pause_state
        self._pause_state = None
