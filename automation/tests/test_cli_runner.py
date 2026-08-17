import unittest
import os
import json
import subprocess
from unittest.mock import patch, MagicMock
from automation.cli_runner import CLIRunner
from automation.models import CommandSpec
from automation.config import PROJECT_ROOT
import automation.config as config
from pathlib import Path
from automation.adapters.codex_adapter import CodexAdapter

class TestCLIRunner(unittest.TestCase):
    def setUp(self):
        self.original_mode = config.HARNESS_MODE
        config.HARNESS_MODE = "H2_READ_ONLY"

    def tearDown(self):
        config.HARNESS_MODE = self.original_mode

    def test_allowlist_enforcement(self):
        runner = CLIRunner()
        cmd = CommandSpec(executable="rm", args=["-rf", "/"], cwd=PROJECT_ROOT, safe_mode=False)
        with self.assertRaises(ValueError):
            runner.run(cmd)

    def test_wrong_cwd_prevention(self):
        runner = CLIRunner()
        cmd = CommandSpec(executable="codex", args=[], cwd="C:\\Windows", safe_mode=True)
        with self.assertRaises(ValueError):
            runner.run(cmd)

    def test_mode_enforcement(self):
        config.HARNESS_MODE = "DRY_RUN_MODE"
        runner = CLIRunner()
        cmd = CommandSpec(executable="codex", args=[], cwd=PROJECT_ROOT, safe_mode=True)
        with self.assertRaises(RuntimeError):
            runner.run(cmd)

    @patch('subprocess.run')
    def test_mock_codex_parsing_success(self, mock_run):
        config.HARNESS_MODE = "H2_READ_ONLY"
        runner = CLIRunner()
        runner.resolve_executable = lambda p: (Path("dummy"), "mock")
        cmd = CommandSpec(executable="codex", args=["exec", "Create plan"], cwd=PROJECT_ROOT, safe_mode=True)
        
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps({"summary": "test", "risk_level": "GREEN"})
        mock_run.return_value.stderr = ""
        
        result = runner.run(cmd)
        
        self.assertEqual(result["exit_code"], 0)
        parsed = json.loads(result["stdout"])
        self.assertIn("summary", parsed)
        self.assertIn("risk_level", parsed)
        self.assertEqual(parsed["risk_level"], "GREEN")

    def test_invalid_executable_rejection(self):
        runner = CLIRunner()
        with self.assertRaises(ValueError):
            runner.resolve_executable("invalid_cli")

    @patch.dict(os.environ, {"CODEX_EXECUTABLE": "C:\\fake\\codex.exe"})
    def test_env_executable_resolution(self):
        runner = CLIRunner()
        with patch('pathlib.Path.is_file', return_value=True):
            path, src = runner.resolve_executable("codex")
            self.assertEqual(str(path), "C:\\fake\\codex.exe")
            self.assertEqual(src, "env")

    @patch('shutil.which', return_value="C:\\path\\agy.exe")
    def test_path_executable_resolution(self, mock_which):
        runner = CLIRunner()
        env = os.environ.copy()
        env.pop("CODEX_EXECUTABLE", None)
        env.pop("ANTIGRAVITY_EXECUTABLE", None)
        with patch.dict(os.environ, env, clear=True):
            with patch('pathlib.Path.is_file', return_value=True):
                path, src = runner.resolve_executable("agy")
                self.assertEqual(str(path), "C:\\path\\agy.exe")
                self.assertEqual(src, "path")

    def test_default_location_resolution(self):
        runner = CLIRunner()
        env = os.environ.copy()
        env.pop("CODEX_EXECUTABLE", None)
        env.pop("ANTIGRAVITY_EXECUTABLE", None)
        with patch.dict(os.environ, env, clear=True):
            with patch('shutil.which', return_value=None):
                with patch('pathlib.Path.is_file', return_value=True):
                    path, src = runner.resolve_executable("codex")
                    self.assertEqual(src, "default_location")
                    self.assertTrue(str(path).endswith("codex.exe"))

    def test_real_mode_mock_rejection(self):
        config.HARNESS_MODE = "H2_REAL_READ_ONLY"
        runner = CLIRunner()
        runner.resolve_executable = lambda p: (Path("dummy"), "mock")
        cmd = CommandSpec(executable="codex", args=["exec", "test"], cwd=PROJECT_ROOT, safe_mode=True)
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "real_output"
            mock_run.return_value.stderr = ""
            result = runner.run(cmd)
            self.assertFalse(result["mock_used"])

    @patch('subprocess.run')
    def test_timeout_mapping_and_partial_stdout(self, mock_run):
        runner = CLIRunner()
        runner.resolve_executable = lambda p: (Path("dummy"), "mock")
        cmd = CommandSpec(executable="codex", args=["exec", "test"], cwd=PROJECT_ROOT, safe_mode=True)
        
        # Simulate TimeoutExpired
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["dummy", "exec", "test"],
            timeout=300,
            output=b"partial stdout",
            stderr=b"partial stderr"
        )
        
        result = runner.run(cmd)
        self.assertEqual(result["exit_code"], -1)
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["stdout"], "partial stdout")
        self.assertEqual(result["stderr"], "partial stderr")

    def test_role_specific_timeout_selection(self):
        runner = CLIRunner()
        runner.resolve_executable = lambda p: (Path("dummy"), "mock")
        
        cmd_plan = CommandSpec(executable="codex", args=["exec", "Create plan"], cwd=PROJECT_ROOT, safe_mode=True)
        cmd_review = CommandSpec(executable="codex", args=["exec", "Review input:"], cwd=PROJECT_ROOT, safe_mode=True)
        cmd_agy = CommandSpec(executable="agy", args=[], cwd=PROJECT_ROOT, safe_mode=True)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            runner.run(cmd_plan)
            self.assertEqual(mock_run.call_args[1]["timeout"], config.CODEX_PLAN_TIMEOUT_SECONDS)
            
            runner.run(cmd_review)
            self.assertEqual(mock_run.call_args[1]["timeout"], config.CODEX_REVIEW_TIMEOUT_SECONDS)
            
            runner.run(cmd_agy)
            self.assertEqual(mock_run.call_args[1]["timeout"], config.ANTIGRAVITY_TIMEOUT_SECONDS)

    def test_invalid_schema_path_rejection(self):
        adapter = CodexAdapter()
        with patch('os.path.exists', return_value=False):
            with self.assertRaises(FileNotFoundError):
                adapter.build_plan_command("test")

    def test_output_schema_command_construction(self):
        adapter = CodexAdapter()
        with patch('os.path.exists', return_value=True):
            cmd = adapter.build_plan_command("test")
            self.assertIn("--output-schema", cmd.args)
            schema_idx = cmd.args.index("--output-schema")
            self.assertTrue(cmd.args[schema_idx+1].endswith("senior_plan.schema.json"))

if __name__ == "__main__":
    unittest.main()
