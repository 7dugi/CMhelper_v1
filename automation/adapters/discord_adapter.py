from typing import Dict, Any
from ..config import DRY_RUN

class DiscordAdapter:
    def build_event_payload(self, event_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": event_type,
            "details": details
        }

    def send_event(self, event: Dict[str, Any]) -> bool:
        if DRY_RUN:
            return True
        # Actual HTTP POST logic here in H2
        # Network errors should be caught and not crash Orchestrator
        return True
