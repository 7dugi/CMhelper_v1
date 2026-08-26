"""Regression tests for EvidenceExecutor profile allowlisting, command shapes, and isolated build validation."""
import unittest
from unittest.mock import MagicMock, patch
import os
import sys
from pathlib import Path

from automation.evidence_executor import EvidenceExecutor


class TestEvidenceExecutorProfiles(unittest.TestCase):
    def setUp(self):
        self.executor = EvidenceExecutor()

    def test_unknown_profile_raises_value_error_fail_closed(self):
        with self.assertRaises(ValueError):
            self.executor.run_tests("unapproved_profile")
        with self.assertRaises(ValueError):
            self.executor.run_tests("arbitrary_command")

    def test_product_validation_profiles_allowlist_is_bounded(self):
        expected_profiles = {
            "cmhelper_phase3d_backend",
            "cmhelper_phase3d_frontend_build",
            "cmhelper_pc_agent_auth",
            "cmhelper_pc_agent_auth_build",
        }
        self.assertEqual(set(self.executor.PRODUCT_VALIDATION_PROFILES.keys()), expected_profiles)

    def test_cmhelper_pc_agent_auth_test_profile_runs_unittest(self):
        with patch.object(self.executor, "_run_safe") as mock_run_safe:
            mock_run_safe.return_value = {"exit_code": 0, "stdout": "Ran 8 tests... OK", "stderr": ""}
            res = self.executor.run_tests("cmhelper_pc_agent_auth")

            self.assertEqual(res["exit_code"], 0)
            mock_run_safe.assert_called_once()
            cmd = mock_run_safe.call_args.args[0]
            kwargs = mock_run_safe.call_args.kwargs

            # Command must be unittest discover without pytest-specific flags
            self.assertIn("-m", cmd)
            self.assertIn("unittest", cmd)
            self.assertIn("discover", cmd)
            self.assertIn("tests", cmd)
            self.assertNotIn("--basetemp", " ".join(str(c) for c in cmd))
            self.assertTrue(kwargs.get("cwd", "").endswith("CMhelper_agent"))

    def test_cmhelper_pc_agent_auth_build_verifies_exe_in_isolated_location(self):
        def fake_run_safe(cmd, cwd=None):
            if "--version" in cmd:
                return {"exit_code": 0, "stdout": "PyInstaller 6.10.0", "stderr": ""}
            # PyInstaller build command: simulate creation of CMhelper_agent.exe in distpath
            if "--distpath" in cmd:
                dist_index = cmd.index("--distpath") + 1
                dist_path = Path(cmd[dist_index])
                dist_path.mkdir(parents=True, exist_ok=True)
                exe_file = dist_path / "CMhelper_agent.exe"
                exe_file.write_bytes(b"MZ_FAKE_EXECUTABLE_BINARY")
                return {"exit_code": 0, "stdout": "Building EXE from CMhelper_agent.spec completed", "stderr": ""}
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        with patch.object(self.executor, "_run_safe", side_effect=fake_run_safe):
            res = self.executor.run_tests("cmhelper_pc_agent_auth_build")

            self.assertEqual(res["exit_code"], 0)
            self.assertIn("Verified executable: CMhelper_agent.exe", res["stdout"])

    def test_cmhelper_pc_agent_auth_build_fails_closed_if_pyinstaller_missing(self):
        def fake_run_safe(cmd, cwd=None):
            if "--version" in cmd:
                return {"exit_code": 1, "stdout": "", "stderr": "No module named PyInstaller"}
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        with patch.object(self.executor, "_run_safe", side_effect=fake_run_safe):
            res = self.executor.run_tests("cmhelper_pc_agent_auth_build")

            self.assertEqual(res["exit_code"], 1)
            self.assertIn("PyInstaller is unavailable", res["stderr"])

    def test_cmhelper_pc_agent_auth_build_fails_closed_if_exe_missing_from_output(self):
        def fake_run_safe(cmd, cwd=None):
            if "--version" in cmd:
                return {"exit_code": 0, "stdout": "PyInstaller 6.10.0", "stderr": ""}
            # Build completes exit 0 but does not create the EXE
            return {"exit_code": 0, "stdout": "build completed with warning", "stderr": ""}

        with patch.object(self.executor, "_run_safe", side_effect=fake_run_safe):
            res = self.executor.run_tests("cmhelper_pc_agent_auth_build")

            self.assertEqual(res["exit_code"], 1)
            self.assertIn("CMhelper_agent.exe was not created", res["stderr"])

    def test_cmhelper_phase3d_backend_profile_preserves_pytest_basetemp(self):
        with patch.object(self.executor, "_run_safe") as mock_run_safe:
            mock_run_safe.return_value = {"exit_code": 0, "stdout": "pytest passed", "stderr": ""}
            res = self.executor.run_tests("cmhelper_phase3d_backend")

            self.assertEqual(res["exit_code"], 0)
            for call in mock_run_safe.call_args_list:
                cmd = call.args[0]
                self.assertTrue(any("--basetemp=" in str(arg) for arg in cmd))
                self.assertTrue(call.kwargs.get("cwd", "").endswith("CMhelper_web\\backend") or call.kwargs.get("cwd", "").endswith("CMhelper_web/backend"))


if __name__ == "__main__":
    unittest.main()
