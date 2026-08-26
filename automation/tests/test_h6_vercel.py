import unittest
from unittest.mock import patch, MagicMock
from automation.adapters.vercel_adapter import VercelAdapter, VercelAdapterError, VercelAccessMode

class TestH6VercelAdapter(unittest.TestCase):
    @patch('automation.adapters.vercel_adapter.os.path.exists')
    def test_linked_project_detection(self, mock_exists):
        mock_exists.return_value = True
        adapter = VercelAdapter()
        self.assertTrue(adapter.is_linked)
        
        mock_exists.return_value = False
        adapter_unlinked = VercelAdapter()
        self.assertFalse(adapter_unlinked.is_linked)

    @patch('automation.adapters.vercel_adapter.subprocess.run')
    @patch('automation.adapters.vercel_adapter.os.path.exists')
    def test_preview_url_parsing(self, mock_exists, mock_run):
        mock_exists.return_value = True
        adapter = VercelAdapter()
        
        # Mocking vercel ls --yes --json
        mock_stdout = '[{"uid": "test-uid", "url": "test-preview.vercel.app", "state": "READY", "created": 123456789}]'
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout)
        
        res = adapter.get_latest_preview()
        self.assertEqual(res.url, "https://test-preview.vercel.app")
        self.assertEqual(res.status, "READY")
        
    @patch('automation.adapters.vercel_adapter.os.path.exists')
    def test_production_deploy_blocked(self, mock_exists):
        mock_exists.return_value = True
        adapter = VercelAdapter(mode=VercelAccessMode.READ_ONLY)
        
        with self.assertRaisesRegex(VercelAdapterError, "Cannot trigger deploy in READ_ONLY mode"):
            adapter.trigger_preview_deploy()

    @patch('automation.adapters.vercel_adapter.subprocess.run')
    @patch('automation.adapters.vercel_adapter.os.path.exists')
    def test_deployment_ready(self, mock_exists, mock_run):
        mock_exists.return_value = True
        adapter = VercelAdapter()
        
        mock_stdout = '[{"uid": "test-uid", "url": "test-preview.vercel.app", "state": "READY", "created": 123456789}]'
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout)
        
        res = adapter.get_latest_preview()
        self.assertEqual(res.status, "READY")

    @patch('automation.adapters.vercel_adapter.subprocess.run')
    @patch('automation.adapters.vercel_adapter.os.path.exists')
    def test_deployment_failed(self, mock_exists, mock_run):
        mock_exists.return_value = True
        adapter = VercelAdapter()
        
        mock_stdout = '[{"uid": "test-uid", "url": "test-preview.vercel.app", "state": "ERROR", "error": "Build failed"}]'
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout)
        
        res = adapter.get_latest_preview()
        self.assertEqual(res.status, "ERROR")
        self.assertEqual(res.error_reason, "Build failed")

    @patch('automation.adapters.vercel_adapter.subprocess.run')
    @patch('automation.adapters.vercel_adapter.os.path.exists')
    def test_no_token_exposure(self, mock_exists, mock_run):
        mock_exists.return_value = True
        adapter = VercelAdapter()
        # Ensure we only pass expected args, no tokens unless through env vars
        mock_run.return_value = MagicMock(returncode=0, stdout='[]')
        adapter.get_latest_preview()
        args = mock_run.call_args[0][0]
        self.assertNotIn("-t", args)
        self.assertNotIn("--token", args)

if __name__ == '__main__':
    unittest.main()
