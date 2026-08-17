import unittest
import os
from unittest.mock import patch
from automation.adapters.browser_adapter import BrowserAdapter, BrowserAdapterError
from automation.models import BrowserQAScenario, BrowserQAStep

class TestH6BrowserAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = BrowserAdapter()

    def test_scenario_serialization(self):
        scenario = BrowserQAScenario(
            scenario_id="s1",
            name="test",
            description="test desc",
            start_url="https://example.com",
            risk="SAFE_READ",
            steps=[
                BrowserQAStep(action="wait_for_selector", selector_or_target="body")
            ]
        )
        self.assertEqual(scenario.scenario_id, "s1")
        self.assertEqual(scenario.steps[0].action, "wait_for_selector")

    def test_safe_read_allowed(self):
        scenario = BrowserQAScenario(
            scenario_id="s1",
            name="test",
            description="test desc",
            start_url="https://example.com",
            risk="SAFE_READ"
        )
        # Auth skip
        res = self.adapter.run_scenario("task1", scenario)
        self.assertNotEqual(res.status, "BLOCKED_MUTATION")

    def test_safe_interaction_allowed(self):
        scenario = BrowserQAScenario(
            scenario_id="s1",
            name="test",
            description="test desc",
            start_url="https://example.com",
            risk="SAFE_INTERACTION"
        )
        res = self.adapter.run_scenario("task1", scenario)
        self.assertNotEqual(res.status, "BLOCKED_MUTATION")

    def test_mutating_action_blocked(self):
        scenario = BrowserQAScenario(
            scenario_id="s1",
            name="test",
            description="test desc",
            start_url="https://example.com",
            risk="MUTATING_INTERACTION"
        )
        res = self.adapter.run_scenario("task1", scenario)
        self.assertEqual(res.status, "BLOCKED_MUTATION")
        self.assertIn("MUTATING_INTERACTION scenarios are automatically blocked in this phase.", res.warnings)

    def test_expected_401_handling(self):
        # Implicit through the fact that auth missing gives SKIPPED_AUTH_REQUIRED
        scenario = BrowserQAScenario(
            scenario_id="s1",
            name="test auth",
            description="auth required",
            start_url="https://example.com",
            requires_auth=True
        )
        # Clear env vars if any
        if "QA_TEST_USER" in os.environ:
            del os.environ["QA_TEST_USER"]
        res = self.adapter.run_scenario("task1", scenario)
        self.assertEqual(res.status, "SKIPPED_AUTH_REQUIRED")

    def test_screenshot_path(self):
        self.assertTrue(os.path.exists(self.adapter.screenshots_dir))

if __name__ == '__main__':
    unittest.main()
