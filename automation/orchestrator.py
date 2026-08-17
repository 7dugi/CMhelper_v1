from typing import List, Dict, Any, Optional
from .models import TaskContext, TaskState, SeniorPlan, ImplementationResult, ReviewResult, ValidationResult
from .config import DRY_RUN, MAX_AUTONOMOUS_REVIEW_ITERATIONS
from .state_machine import StateMachine

class ReviewLoopGuard:
    def __init__(self):
        self.iteration_count = 0
        self.issue_signatures: List[str] = []
        self.implementation_signatures: List[str] = []

    def record_review(self, issues: List[str]):
        self.iteration_count += 1
        sig = "|".join(sorted([issue.lower().strip() for issue in issues]))
        self.issue_signatures.append(sig)

    def record_implementation(self, changed_files: List[str], summary: str):
        sig = f"{'|'.join(sorted(changed_files))}:{hash(summary)}"
        self.implementation_signatures.append(sig)

    def detect_no_progress(self) -> bool:
        if len(self.issue_signatures) >= 2:
            return self.issue_signatures[-1] == self.issue_signatures[-2]
        return False

    def detect_oscillation(self) -> bool:
        if len(self.implementation_signatures) >= 3:
            return self.implementation_signatures[-1] == self.implementation_signatures[-3]
        return False

    def autonomous_limit_reached(self) -> bool:
        return self.iteration_count >= MAX_AUTONOMOUS_REVIEW_ITERATIONS

class PassGate:
    def __init__(self):
        pass
        
    def evaluate(self, plan: SeniorPlan, review: ReviewResult, validation: ValidationResult, approved: bool) -> bool:
        from .models import ReviewStatus
        if review.status != ReviewStatus.PASS:
            return False
            
        for ac in plan.acceptance_criteria:
            if ac.required and ac.status != "PASS":
                return False
                
        if not validation.all_required_passed(plan.required_validations):
            return False
            
        if plan.user_decision_required and not approved:
            return False
            
        return True

class Orchestrator:
    def __init__(self, context: TaskContext):
        self.context = context
        self.sm = StateMachine(context.task.state)
        self.loop_guard = ReviewLoopGuard()
        self.pass_gate = PassGate()

    def prepare_task(self):
        self.sm.transition(TaskState.PRE_FLIGHT)

    def load_context(self):
        self.sm.transition(TaskState.CONTEXT_LOADING)

    def create_plan(self):
        self.sm.transition(TaskState.PLANNING)

    def request_implementation(self):
        self.sm.transition(TaskState.IMPLEMENTING)

    def review_result(self):
        self.sm.transition(TaskState.REVIEWING)

    def evaluate_validation(self):
        self.sm.transition(TaskState.VALIDATING)

    def handle_review_result(self, result: ReviewResult):
        from .models import ReviewStatus
        self.loop_guard.record_review(result.issues)
        
        if result.status == ReviewStatus.REVISE:
            if self.loop_guard.autonomous_limit_reached() or self.loop_guard.detect_no_progress() or self.loop_guard.detect_oscillation():
                self.sm.transition(TaskState.FAILED_STALLED)
            else:
                self.sm.transition(TaskState.REVISING)
        elif result.status == ReviewStatus.NEED_USER_DECISION:
            self.sm.transition(TaskState.NEED_USER_DECISION)
        elif result.status == ReviewStatus.FAILED_STALLED:
            self.sm.transition(TaskState.FAILED_STALLED)
        elif result.status == ReviewStatus.PASS:
            self.sm.transition(TaskState.VALIDATING)

    def handle_stall(self):
        self.sm.transition(TaskState.FAILED_STALLED)

    def handle_approval(self):
        if self.sm.current_state == TaskState.NEED_USER_DECISION:
            self.sm.resume_state()

    def can_commit(self, plan: SeniorPlan, review: ReviewResult, val: ValidationResult, approved: bool) -> bool:
        if self.pass_gate.evaluate(plan, review, val, approved):
            self.sm.transition(TaskState.READY_TO_COMMIT)
            return True
        return False
