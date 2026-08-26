from .base import SeniorAgent
from ..models import TaskContext, SeniorPlan, ImplementationResult, ReviewResult, ValidationResult

class DefaultSenior(SeniorAgent):
    def create_plan(self, context: TaskContext) -> SeniorPlan:
        # Implementation via adapter
        raise NotImplementedError

    def review(self, context: TaskContext, implementation_result: ImplementationResult, validation_result: ValidationResult) -> ReviewResult:
        raise NotImplementedError

    def evaluate_evidence(self, context: TaskContext, result: any) -> any:
        raise NotImplementedError
