from typing import Dict, List, Optional
from .models import TaskState

TRANSITIONS: Dict[TaskState, List[TaskState]] = {
    TaskState.NEW: [TaskState.PRE_FLIGHT],
    TaskState.PRE_FLIGHT: [TaskState.CONTEXT_LOADING, TaskState.FAILED],
    TaskState.CONTEXT_LOADING: [TaskState.PLANNING, TaskState.NEED_USER_DECISION, TaskState.FAILED],
    TaskState.QUEUED: [TaskState.IDLE, TaskState.FAILED],
    TaskState.IDLE: [TaskState.PLANNING],
    TaskState.PLANNING: [TaskState.DESIGNING, TaskState.IMPLEMENTING, TaskState.NEED_USER_DECISION, TaskState.WAITING_FOR_QUOTA, TaskState.PAUSED],
    TaskState.DESIGNING: [TaskState.IMPLEMENTING, TaskState.NEED_USER_DECISION, TaskState.WAITING_FOR_QUOTA, TaskState.PAUSED],
    TaskState.IMPLEMENTING: [TaskState.VALIDATING, TaskState.NEED_USER_DECISION, TaskState.WAITING_FOR_QUOTA, TaskState.FAILED, TaskState.REVIEWING, TaskState.PAUSED],
    TaskState.VALIDATING: [TaskState.TESTING, TaskState.BUILDING, TaskState.DB_INSPECTION, TaskState.PREVIEW_DEPLOY, TaskState.REVIEWING, TaskState.READY_TO_COMMIT, TaskState.REVISING, TaskState.PAUSED],
    TaskState.TESTING: [TaskState.BUILDING, TaskState.REVIEWING, TaskState.REVISING, TaskState.VALIDATING, TaskState.PAUSED],
    TaskState.BUILDING: [TaskState.REVIEWING, TaskState.REVISING, TaskState.VALIDATING, TaskState.PAUSED],
    TaskState.DB_INSPECTION: [TaskState.PREVIEW_DEPLOY, TaskState.REVIEWING, TaskState.REVISING, TaskState.VALIDATING, TaskState.PAUSED],
    TaskState.PREVIEW_DEPLOY: [TaskState.BROWSER_QA_PLANNING, TaskState.REVIEWING, TaskState.REVISING, TaskState.VALIDATING, TaskState.PAUSED],
    TaskState.BROWSER_QA_PLANNING: [TaskState.BROWSER_QA_EXECUTION, TaskState.REVIEWING, TaskState.REVISING, TaskState.VALIDATING, TaskState.PAUSED],
    TaskState.BROWSER_QA_EXECUTION: [TaskState.FINAL_REVIEW, TaskState.REVIEWING, TaskState.REVISING, TaskState.VALIDATING, TaskState.PAUSED],
    TaskState.FINAL_REVIEW: [TaskState.READY_TO_COMMIT, TaskState.REVIEWING, TaskState.REVISING, TaskState.VALIDATING, TaskState.PAUSED],
    TaskState.REVIEWING: [TaskState.DB_INSPECTION, TaskState.READY_TO_COMMIT, TaskState.REVISING, TaskState.VALIDATING, TaskState.NEED_USER_DECISION, TaskState.WAITING_FOR_QUOTA, TaskState.FAILED_STALLED, TaskState.PAUSED],
    TaskState.REVISING: [TaskState.IMPLEMENTING, TaskState.NEED_USER_DECISION, TaskState.FAILED_STALLED, TaskState.PAUSED],
    TaskState.READY_TO_COMMIT: [TaskState.COMMITTED, TaskState.COMMITTING, TaskState.WAITING_FOR_USER_APPROVAL, TaskState.PAUSED],
    TaskState.WAITING_FOR_USER_APPROVAL: [TaskState.APPROVED_TO_COMMIT, TaskState.REJECTED_BY_USER, TaskState.COMMITTED, TaskState.COMMITTING, TaskState.PUSHING, TaskState.FAILED_STALLED, TaskState.NEED_USER_DECISION, TaskState.PAUSED],
    TaskState.APPROVED_TO_COMMIT: [TaskState.COMMITTING, TaskState.COMMITTED],
    TaskState.REJECTED_BY_USER: [TaskState.IDLE, TaskState.FAILED_STALLED, TaskState.NEED_USER_DECISION],
    TaskState.WAITING_FOR_QUOTA: [TaskState.RESUMING, TaskState.FAILED_STALLED, TaskState.PAUSED],
    TaskState.RESUMING: [TaskState.PLANNING, TaskState.DESIGNING, TaskState.IMPLEMENTING, TaskState.REVIEWING, TaskState.FAILED_STALLED, TaskState.PAUSED, TaskState.COMMITTING, TaskState.PUSHING],
    TaskState.PAUSED: [TaskState.RESUMING, TaskState.FAILED_STALLED],
    TaskState.COMMITTING: [TaskState.WAITING_FOR_USER_APPROVAL, TaskState.COMPLETED, TaskState.FAILED],
    TaskState.COMMITTED: [TaskState.PUSHED, TaskState.PUSHING],
    TaskState.PUSHING: [TaskState.COMPLETED, TaskState.FAILED],
    TaskState.PUSHED: [TaskState.IDLE, TaskState.COMPLETED],
    TaskState.COMPLETED: [],
    TaskState.FAILED: [],
    TaskState.NEED_USER_DECISION: [TaskState.PLANNING, TaskState.IMPLEMENTING, TaskState.FAILED_STALLED],
    TaskState.FAILED_STALLED: [TaskState.IDLE]
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
