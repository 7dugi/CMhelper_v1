from pydantic import BaseModel
from typing import Optional
from ..config import DRY_RUN

class VercelResult(BaseModel):
    preview_url: str = ""
    deployment_status: str = "PENDING"
    error: str = ""

class VercelAdapter:
    def request_preview(self) -> VercelResult:
        if DRY_RUN:
            return VercelResult(preview_url="https://preview.local", deployment_status="SUCCESS")
        raise NotImplementedError

    def get_preview_status(self) -> VercelResult:
        if DRY_RUN:
            return VercelResult(preview_url="https://preview.local", deployment_status="SUCCESS")
        raise NotImplementedError
