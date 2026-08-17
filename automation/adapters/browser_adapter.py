from pydantic import BaseModel
from typing import List, Dict
from ..config import DRY_RUN

class BrowserQAResult(BaseModel):
    url: str
    scenario: str
    navigation_status: str
    actions: List[Dict[str, str]] = []
    screenshots: List[str] = []
    console_errors: List[str] = []
    network_errors: List[str] = []
    desktop_status: str = ""
    mobile_status: str = ""
    overall_status: str = "NOT_RUN"

class BrowserAdapter:
    def run_scenario(self, url: str, scenario: str) -> BrowserQAResult:
        if DRY_RUN:
            return BrowserQAResult(
                url=url, 
                scenario=scenario, 
                navigation_status="SUCCESS", 
                overall_status="PASS"
            )
        raise NotImplementedError
