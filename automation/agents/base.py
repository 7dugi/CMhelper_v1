from typing import Optional, Any
from ..models import TaskContext, SeniorPlan, ImplementationResult, ReviewResult, ValidationResult

class SeniorAgent:
    def create_plan(self, context: TaskContext) -> SeniorPlan:
        raise NotImplementedError

    def review(self, context: TaskContext, implementation_result: ImplementationResult, validation_result: ValidationResult) -> ReviewResult:
        raise NotImplementedError

    def evaluate_evidence(self, context: TaskContext, result: Any) -> Any:
        raise NotImplementedError

class ImplementerAgent:
    def analyze_plan(self, plan: SeniorPlan) -> Any:
        raise NotImplementedError

    def implement(self, plan: SeniorPlan) -> ImplementationResult:
        raise NotImplementedError

    def revise(self, review_result: ReviewResult) -> ImplementationResult:
        raise NotImplementedError

class DesignerAgent:
    def create_design_spec(self, plan: SeniorPlan) -> Any:
        raise NotImplementedError

    def review_ui(self, ui_result: Any) -> Any:
        raise NotImplementedError
