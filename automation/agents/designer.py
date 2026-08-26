from .base import DesignerAgent
from ..models import SeniorPlan

class DefaultDesigner(DesignerAgent):
    def create_design_spec(self, plan: SeniorPlan) -> any:
        raise NotImplementedError

    def review_ui(self, ui_result: any) -> any:
        raise NotImplementedError
