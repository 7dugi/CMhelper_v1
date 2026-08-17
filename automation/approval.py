from .models import RiskLevel

RED_KEYWORDS = [
    "production db schema change",
    "production data mutation",
    "drop",
    "truncate",
    "bulk delete",
    "bulk update",
    "rls",
    "auth",
    "secret",
    "env mutation",
    "force push",
    "destructive git",
    "main merge",
    "production deploy"
]

class RiskEvaluator:
    def classify(self, action: str) -> RiskLevel:
        action_lower = action.lower()
        for kw in RED_KEYWORDS:
            if kw in action_lower:
                return RiskLevel.RED
        
        if "update" in action_lower or "delete" in action_lower or "modify" in action_lower:
            return RiskLevel.YELLOW
            
        return RiskLevel.GREEN

    def requires_user_approval(self, risk: RiskLevel) -> bool:
        return risk == RiskLevel.RED
