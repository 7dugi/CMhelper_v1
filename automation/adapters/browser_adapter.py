import os
import time
from typing import Optional, List
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, Page, Error as PlaywrightError

from ..models import BrowserQAScenario, BrowserQAResult, BrowserQAStep, StepResult
from ..secret_masker import SecretMasker

class BrowserAdapterError(Exception):
    pass

class BrowserAdapter:
    def __init__(self, root_dir: str = "."):
        self.root_dir = root_dir
        self.screenshots_dir = os.path.join(self.root_dir, "automation", "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)

    def _mask_url(self, url: str) -> str:
        return SecretMasker.mask(url)

    def _execute_step(self, page: Page, step: BrowserQAStep, result_path: str) -> StepResult:
        step_res = StepResult(action=step.action, status="PENDING")
        try:
            if step.action == "wait_for_selector":
                page.wait_for_selector(step.selector_or_target, timeout=step.timeout)
                step_res.status = "PASS"
            elif step.action == "click":
                page.click(step.selector_or_target, timeout=step.timeout)
                step_res.status = "PASS"
            elif step.action == "fill":
                page.fill(step.selector_or_target, step.expected or "", timeout=step.timeout)
                step_res.status = "PASS"
            elif step.action == "assert_text":
                locator = page.locator(step.selector_or_target)
                text = locator.inner_text(timeout=step.timeout)
                if step.expected and step.expected not in text:
                    step_res.status = "FAIL"
                    step_res.actual = text
                    step_res.error = f"Expected '{step.expected}' not in '{text}'"
                else:
                    step_res.status = "PASS"
                    step_res.actual = text
            else:
                step_res.status = "UNKNOWN_ACTION"
                step_res.error = f"Action {step.action} not supported."

            if step.screenshot_after and step_res.status == "PASS":
                screenshot_file = os.path.join(result_path, f"{step.action}_{int(time.time())}.png")
                page.screenshot(path=screenshot_file)
                step_res.screenshot = screenshot_file

        except PlaywrightError as e:
            step_res.status = "FAIL"
            step_res.error = str(e)
            
            # capture failure screenshot
            screenshot_file = os.path.join(result_path, f"failure_{step.action}_{int(time.time())}.png")
            try:
                page.screenshot(path=screenshot_file)
                step_res.screenshot = screenshot_file
            except Exception:
                pass

        return step_res

    def run_scenario(self, task_id: str, scenario: BrowserQAScenario) -> BrowserQAResult:
        if scenario.risk == "MUTATING_INTERACTION":
            return BrowserQAResult(
                scenario_id=scenario.scenario_id,
                status="BLOCKED_MUTATION",
                warnings=["MUTATING_INTERACTION scenarios are automatically blocked in this phase."]
            )

        if scenario.requires_auth:
            test_user = os.environ.get("QA_TEST_USER")
            test_pass = os.environ.get("QA_TEST_PASS")
            if not test_user or not test_pass:
                return BrowserQAResult(
                    scenario_id=scenario.scenario_id,
                    status="SKIPPED_AUTH_REQUIRED",
                    warnings=["No test credentials provided via QA_TEST_USER/QA_TEST_PASS."]
                )

        result_path = os.path.join(self.screenshots_dir, task_id, scenario.scenario_id)
        os.makedirs(result_path, exist_ok=True)

        res = BrowserQAResult(
            scenario_id=scenario.scenario_id,
            status="RUNNING",
            started_at=datetime.now(timezone.utc)
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                viewport = {"width": 375, "height": 812} if scenario.is_mobile else {"width": 1280, "height": 720}
                context = browser.new_context(
                    viewport=viewport,
                    is_mobile=scenario.is_mobile,
                    has_touch=scenario.is_mobile,
                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1" if scenario.is_mobile else None
                )
                # Apply Vercel Bypass Secret if present
                bypass_secret = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET")
                if bypass_secret:
                    from urllib.parse import urlparse
                    target_netloc = urlparse(scenario.start_url).netloc
                    
                    def handle_route(route, request):
                        req_netloc = urlparse(request.url).netloc
                        if req_netloc == target_netloc:
                            headers = request.headers
                            headers["x-vercel-protection-bypass"] = bypass_secret
                            route.continue_(headers=headers)
                        else:
                            route.continue_()
                            
                    context.route("**/*", handle_route)
                    
                page = context.new_page()

                # Event listeners for Console
                def on_console(msg):
                    if msg.type in ['error', 'warning']:
                        text = self._mask_url(msg.text)
                        res.console_errors.append(f"[{msg.type.upper()}] {text}")

                def on_pageerror(exception):
                    err = self._mask_url(str(exception))
                    res.console_errors.append(f"[FATAL_ERROR] {err}")

                # Event listeners for Network
                def on_response(response):
                    if response.status >= 400:
                        url = self._mask_url(response.url)
                        res.network_errors.append(f"[HTTP_{response.status}] {response.request.method} {url}")

                def on_requestfailed(request):
                    url = self._mask_url(request.url)
                    failure = request.failure
                    err_text = failure if failure else "Unknown network failure"
                    res.network_errors.append(f"[NETWORK_FAILURE] {request.method} {url} - {err_text}")

                page.on("console", on_console)
                page.on("pageerror", on_pageerror)
                page.on("response", on_response)
                page.on("requestfailed", on_requestfailed)

                # Navigation
                page.goto(scenario.start_url, wait_until="networkidle", timeout=15000)
                
                # Execute Steps
                for step in scenario.steps:
                    step_res = self._execute_step(page, step, result_path)
                    res.steps.append(step_res)
                    if step_res.status == "FAIL":
                        res.status = "FAIL"
                        break
                        
                if res.status != "FAIL":
                    res.status = "PASS"
                    
                res.final_url = self._mask_url(page.url)
                
                # Final screenshot
                final_screenshot = os.path.join(result_path, f"final_{int(time.time())}.png")
                page.screenshot(path=final_screenshot)
                res.screenshots.append(final_screenshot)
                
                # Collect step screenshots
                for s in res.steps:
                    if s.screenshot:
                        res.screenshots.append(s.screenshot)

                context.close()
                browser.close()
                
        except Exception as e:
            res.status = "FAIL"
            res.warnings.append(str(e))
            
        res.finished_at = datetime.now(timezone.utc)
        return res
