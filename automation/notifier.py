import json
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Any
from .secret_masker import SecretMasker

class NotificationSeverity:
    DEBUG = "DEBUG"
    INFO = "INFO"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    ERROR = "ERROR"

class NotificationEvent(BaseModel):
    event_type: str
    message: str
    task_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    severity: str = NotificationSeverity.INFO
    stage: Optional[str] = None
    iteration: Optional[int] = None
    details: Optional[Any] = None

class Notifier(ABC):
    @abstractmethod
    def notify(self, event: NotificationEvent):
        pass

class ConsoleNotifier(Notifier):
    def notify(self, event: NotificationEvent):
        masked_msg = SecretMasker.mask(event.message)
        print(f"[{event.timestamp.isoformat()}] [{event.severity}] {event.event_type} - {event.task_id}: {masked_msg}")

class FileNotifier(Notifier):
    def __init__(self, log_path: str):
        self.log_path = log_path

    def notify(self, event: NotificationEvent):
        masked_event = event.model_copy()
        masked_event.message = SecretMasker.mask(masked_event.message)
        if isinstance(masked_event.details, str):
            masked_event.details = SecretMasker.mask(masked_event.details)
        elif isinstance(masked_event.details, dict):
            masked_event.details = json.loads(SecretMasker.mask(json.dumps(masked_event.details)))
            
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(masked_event.model_dump_json() + "\n")

class DiscordNotifier(Notifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _mask_url(self, url: str) -> str:
        if not url:
            return ""
        if len(url) > 20:
            return url[:8] + "..." + url[-4:]
        return "***"

    def notify(self, event: NotificationEvent):
        if not self.webhook_url:
            return
            
        if event.severity == NotificationSeverity.DEBUG:
            return
            
        masked_msg = SecretMasker.mask(event.message)
        payload = {
            "content": f"**[{event.severity}] {event.event_type}**\nTask: `{event.task_id}`\n{masked_msg}"
        }
        
        try:
            req = urllib.request.Request(
                self.webhook_url, 
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            # Fallback will be handled by Audit Logger capturing delivery failure
            from .audit_logger import AuditLogger
            audit = AuditLogger(event.task_id)
            masked_url = self._mask_url(self.webhook_url)
            audit.log_event("AUDIT_DELIVERY_FAILED", {
                "reason": str(e),
                "url": masked_url,
                "original_event_type": event.event_type
            })
            print(f"Failed to send Discord notification to {masked_url}: {e}")
