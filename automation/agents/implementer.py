from .base import ImplementerAgent
from ..models import SeniorPlan, ImplementationResult, ReviewResult

class DefaultImplementer(ImplementerAgent):
    def analyze_plan(self, plan: SeniorPlan) -> any:
        raise NotImplementedError

    def implement(self, plan: SeniorPlan) -> ImplementationResult:
        raise NotImplementedError

    def revise(self, review_result: ReviewResult) -> ImplementationResult:
        raise NotImplementedError
