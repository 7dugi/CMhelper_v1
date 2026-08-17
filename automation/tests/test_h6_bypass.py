import unittest
import os
from unittest.mock import patch, MagicMock
from automation.adapters.browser_adapter import BrowserAdapter
from automation.models import BrowserQAScenario, BrowserQAStep
from automation.secret_masker import SecretMasker

class TestH6Bypass(unittest.TestCase):
    def test_bypass_secret_masked(self):
        # Mock environment
        with patch.dict(os.environ, {"VERCEL_AUTOMATION_BYPASS_SECRET": "my-secret-123"}):
            text = "Here is my-secret-123 in a log."
            masked = SecretMasker.mask(text)
            self.assertIn("***VERCEL_BYPASS_SECRET_MASKED***", masked)
            self.assertNotIn("my-secret-123", masked)
            
    def test_bypass_secret_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            text = "Here is some text."
            self.assertEqual(SecretMasker.mask(text), text)

    @patch('automation.adapters.browser_adapter.sync_playwright')
    def test_bypass_header_injection(self, mock_playwright):
        # Setup mock playwright
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_browser = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        adapter = BrowserAdapter()
        scenario = BrowserQAScenario(
            scenario_id="s1",
            name="test",
            description="test desc",
            start_url="https://example.com",
            risk="SAFE_READ"
        )
        
        with patch.dict(os.environ, {"VERCEL_AUTOMATION_BYPASS_SECRET": "test-secret"}):
            adapter.run_scenario("task1", scenario)
            # Verify route was set
            from unittest.mock import ANY
            mock_context.route.assert_called_with("**/*", ANY)

if __name__ == '__main__':
    unittest.main()
