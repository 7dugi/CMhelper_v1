import os
import json
from datetime import datetime
from typing import Dict, Any

from .config import PROJECT_ROOT

class AuditLogger:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.report_dir = os.path.join(PROJECT_ROOT, "automation", "reports", task_id)
        os.makedirs(self.report_dir, exist_ok=True)
        self.events_file = os.path.join(self.report_dir, "events.jsonl")

    def _mask_secrets(self, data: str) -> str:
        # Simple mask helper
        masked = data.replace("VERCEL_TOKEN=", "VERCEL_TOKEN=***")
        masked = masked.replace("DISCORD_WEBHOOK_URL=", "DISCORD_WEBHOOK_URL=***")
        return masked

    def log_event(self, event_type: str, details: Dict[str, Any]):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "details": details
        }
        
        try:
            with open(self.events_file, "a", encoding="utf-8") as f:
                raw_str = json.dumps(event, ensure_ascii=False)
                masked_str = self._mask_secrets(raw_str)
                f.write(masked_str + "\n")
        except Exception:
            pass # Audit failure should not crash workflow if non-critical

    def save_json(self, filename: str, data: Dict[str, Any]):
        try:
            with open(os.path.join(self.report_dir, filename), "w", encoding="utf-8") as f:
                raw_str = json.dumps(data, ensure_ascii=False, indent=2)
                f.write(self._mask_secrets(raw_str))
        except Exception:
            pass

    def save_text(self, filename: str, text: str):
        try:
            with open(os.path.join(self.report_dir, filename), "w", encoding="utf-8") as f:
                f.write(self._mask_secrets(text))
        except Exception:
            pass
