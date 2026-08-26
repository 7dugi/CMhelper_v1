import subprocess
import os
import shutil
import hashlib
import sys
import tempfile
from pathlib import Path
from automation.config import PROJECT_ROOT

class EvidenceExecutor:
    """
    Harness component responsible for executing safe, pre-defined commands
    to gather evidence, ensuring Antigravity does not run raw shell commands.
    """

    ALLOWED_PROFILES = {
        "tests": ["python", "-m", "unittest", "discover", "-s", "automation/tests"],
        "compileall": ["python", "-m", "compileall", "automation/"],
        "harness_tests": ["python", "-m", "unittest", "discover", "-s", "automation/tests"],
    }
    PRODUCT_VALIDATION_PROFILES = {
        "cmhelper_phase3d_backend": {
            "cwd": "CMhelper_web/backend",
            "use_python": True,
            "commands": [
                ["-m", "pytest", "tests/test_opportunity_conversion.py", "-v"],
                ["-m", "pytest", "tests/test_auth.py", "tests/test_opportunity_conversion.py", "-v"],
                ["-m", "pytest", "tests/test_opportunity_conversion.py", "tests/test_auth.py", "-v"],
                ["-m", "pytest", "tests/test_migrations.py", "-v"],
                ["-m", "pytest", "tests/", "-v"],
            ],
        },
        "cmhelper_phase3d_frontend_build": {
            "cwd": "CMhelper_web/frontend",
            "use_python": False,
            "commands": [
                ["npm", "run", "build"],
            ],
        },
        "cmhelper_pc_agent_auth": {
            "cwd": "CMhelper_agent",
            "use_python": True,
            "commands": [
                ["-m", "unittest", "discover", "-s", "tests", "-v"],
            ],
        },
        "cmhelper_pc_agent_auth_build": {
            "cwd": "CMhelper_agent",
            "use_python": True,
            "is_build": True,
            "commands": [
                ["-m", "PyInstaller", "CMhelper_agent.spec", "--noconfirm"],
            ],
        },
    }

    def __init__(self, cwd: str = PROJECT_ROOT):
        self.cwd = cwd
        self.baseline_status = {}
        canonical_python = Path(cwd) / ".venv" / "Scripts" / "python.exe"
        self.python_executable = str(canonical_python) if canonical_python.is_file() else sys.executable

    def _get_current_changed_files(self) -> set:
        """Returns a set of all currently changed and untracked files."""
        status_out = self._run_git(["status", "--short"])
        files = set()
        for line in status_out.splitlines():
            if len(line) > 2:
                # ' M file.py', '?? new_file.py'
                files.add(line[3:].strip())
        return files

    def capture_repo_snapshot(self) -> str:
        """Captures git status and git diff."""
        status = self._run_git(["status", "--short"])
        diff = self._run_git(["diff", "--name-only"])
        return f"STATUS:\n{status}\nDIFF:\n{diff}"

    def capture_baseline(self):
        """Capture dirty-worktree paths and contents immediately before implementation."""
        self.baseline_status = self._get_dirty_worktree_snapshot()

    def get_actual_new_mutation(self) -> list:
        """Return only dirty-worktree paths whose state/content changed since the baseline."""
        current_status = self._get_dirty_worktree_snapshot()
        paths = set(self.baseline_status) | set(current_status)
        return sorted(path for path in paths if self.baseline_status.get(path) != current_status.get(path))

    def _get_dirty_worktree_snapshot(self) -> dict:
        """Map every dirty path to its porcelain status and content fingerprint."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                cwd=self.cwd,
                capture_output=True,
                check=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Unable to capture Git worktree baseline: {exc}") from exc

        snapshot = {}
        for record in result.stdout.decode("utf-8", "surrogateescape").split("\0"):
            if not record or len(record) < 4:
                continue
            status, raw_path = record[:2], record[3:]
            path = Path(self.cwd) / raw_path
            snapshot[raw_path] = (status, self._fingerprint(path))
        return snapshot

    @staticmethod
    def _fingerprint(path: Path) -> str:
        if not path.exists() and not path.is_symlink():
            return "MISSING"
        if path.is_symlink():
            return f"SYMLINK:{path.readlink()}"
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
        digest = hashlib.sha256()
        for child in sorted(path.rglob("*")):
            if child.is_file():
                digest.update(str(child.relative_to(path)).encode("utf-8", "surrogateescape"))
                digest.update(child.read_bytes())
        return f"DIRECTORY:{digest.hexdigest()}"

    def capture_git_diff(self) -> str:
        """Captures detailed git diff."""
        return self._run_git(["diff"])

    def capture_changed_files(self) -> list:
        """Returns a list of changed files."""
        out = self._run_git(["diff", "--name-only"])
        return [line.strip() for line in out.splitlines() if line.strip()]

    def get_tracked_repository_files(self) -> list:
        """Return exact repository-relative tracked files for read-only implementer access."""
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                check=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Unable to enumerate tracked repository files: {exc}") from exc
        paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not paths:
            raise RuntimeError("Tracked repository file list is empty; refusing to grant implementer read access")
        return paths

    @staticmethod
    def _resolve_npm_executable() -> str:
        """Locate the fixed Node/npm executable for the frontend build profile.

        A Scheduled Task does not inherit an interactive shell's PATH.  The
        frontend validation profile must therefore resolve npm from a known
        installation location rather than rely on a bare ``npm`` command.
        This remains a fixed Harness-owned command and fails closed when Node
        is not installed.
        """
        fixed_candidates = [
            str(Path(os.environ.get("ProgramFiles", r"C:\\Program Files")) / "nodejs" / "npm.cmd"),
            str(Path(os.environ.get("ProgramW6432", r"C:\\Program Files")) / "nodejs" / "npm.cmd"),
        ]
        for candidate in fixed_candidates:
            if candidate and Path(candidate).is_file():
                return str(Path(candidate))

        # PATH can contain unavailable network locations in a Scheduled Task
        # session.  Use it only after fixed Windows Node.js locations fail.
        for candidate in (shutil.which("npm.cmd"), shutil.which("npm")):
            if candidate and Path(candidate).is_file():
                return str(Path(candidate))
        raise RuntimeError(
            "Required frontend build tool npm.cmd was not found in the supported Node.js installation locations"
        )

    def run_tests(self, profile: str = "tests") -> dict:
        """Runs pre-defined tests from the CMhelper Validation Profile."""
        if profile in self.PRODUCT_VALIDATION_PROFILES:
            profile_config = self.PRODUCT_VALIDATION_PROFILES[profile]
            profile_cwd = str(Path(self.cwd) / profile_config["cwd"])
            task_scope = os.environ.get("HARNESS_TASK_ID", "manual")

            with tempfile.TemporaryDirectory(prefix=f"cmhelper-{profile}-{task_scope}-", ignore_cleanup_errors=True) as temp_root:
                # 1. PyInstaller Build Profile (Isolated executable build and verification)
                if profile_config.get("is_build"):
                    dist_dir = Path(temp_root) / "dist"
                    work_dir = Path(temp_root) / "build"

                    # Verify PyInstaller availability without workarounds or auto-install
                    check_pyinstaller = self._run_safe([self.python_executable, "-m", "PyInstaller", "--version"], cwd=profile_cwd)
                    if check_pyinstaller["exit_code"] != 0:
                        return {
                            "exit_code": 1,
                            "stdout": check_pyinstaller.get("stdout", ""),
                            "stderr": f"PyInstaller is unavailable: {check_pyinstaller.get('stderr', '')}".strip(),
                            "commands": [[self.python_executable, "-m", "PyInstaller", "--version"]],
                        }

                    build_cmd = [
                        self.python_executable,
                        "-m", "PyInstaller",
                        "CMhelper_agent.spec",
                        "--distpath", str(dist_dir),
                        "--workpath", str(work_dir),
                        "--noconfirm",
                    ]
                    build_res = self._run_safe(build_cmd, cwd=profile_cwd)
                    commands = [build_cmd]

                    if build_res["exit_code"] != 0:
                        return {
                            "exit_code": build_res["exit_code"],
                            "stdout": build_res["stdout"],
                            "stderr": build_res["stderr"],
                            "commands": commands,
                        }

                    # Verify CMhelper_agent.exe exists in the isolated dist output directory
                    exe_file = dist_dir / "CMhelper_agent.exe"
                    if not exe_file.is_file():
                        nested_exe = dist_dir / "CMhelper_agent" / "CMhelper_agent.exe"
                        if nested_exe.is_file():
                            exe_file = nested_exe
                        else:
                            return {
                                "exit_code": 1,
                                "stdout": build_res["stdout"],
                                "stderr": f"Build output validation failed: CMhelper_agent.exe was not created in {dist_dir}",
                                "commands": commands,
                            }

                    return {
                        "exit_code": 0,
                        "stdout": build_res["stdout"] + f"\nVerified executable: {exe_file.name} successfully created.",
                        "stderr": build_res["stderr"],
                        "commands": commands,
                    }

                # 2. Python Test Profiles (pytest or unittest)
                if profile_config.get("use_python", True):
                    results = []
                    commands = []
                    for cmd_spec in profile_config["commands"]:
                        if "pytest" in cmd_spec:
                            pytest_base_temp = Path(temp_root) / "pytest"
                            cmd = [self.python_executable, *cmd_spec, f"--basetemp={pytest_base_temp}"]
                        else:
                            cmd = [self.python_executable, *cmd_spec]
                        commands.append(cmd)
                        result = self._run_safe(cmd, cwd=profile_cwd)
                        results.append(result)
                        if result["exit_code"] != 0:
                            break
                    return {
                        "exit_code": 0 if len(results) == len(profile_config["commands"]) and all(item["exit_code"] == 0 for item in results) else 1,
                        "stdout": "\n".join(item["stdout"] for item in results),
                        "stderr": "\n".join(item["stderr"] for item in results),
                        "commands": commands,
                    }

                # 3. Frontend Build Profile (npm)
                npm_executable = self._resolve_npm_executable()
                commands = [
                    [npm_executable if item == "npm" else item for item in command]
                    for command in profile_config["commands"]
                ]
                results = []
                for command in commands:
                    result = self._run_safe(command, cwd=profile_cwd)
                    results.append(result)
                    if result["exit_code"] != 0:
                        break
                return {
                    "exit_code": 0 if len(results) == len(profile_config["commands"]) and all(item["exit_code"] == 0 for item in results) else 1,
                    "stdout": "\n".join(item["stdout"] for item in results),
                    "stderr": "\n".join(item["stderr"] for item in results),
                    "commands": commands,
                }

        if profile not in self.ALLOWED_PROFILES:
            raise ValueError(f"Profile {profile} is not allowed. Choose from {list(self.ALLOWED_PROFILES.keys())}")

        cmd = [self.python_executable if item == "python" else item for item in self.ALLOWED_PROFILES[profile]]
        return self._run_safe(cmd)

    def _run_git(self, args: list) -> str:
        cmd = ["git"] + args
        try:
            res = subprocess.run(cmd, cwd=self.cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
            return res.stdout
        except subprocess.CalledProcessError as e:
            return e.stdout + "\n" + e.stderr
        except Exception as e:
            return str(e)

    def run_git_hygiene(self) -> dict:
        """Run the fixed, read-only Git checks required before review."""
        diff_check = self._run_safe(["git", "diff", "--check"])
        status = self._run_safe(["git", "status", "--short"])
        return {"diff_check": diff_check, "status": status}

    def _run_safe(self, cmd: list, cwd: str = None) -> dict:
        if os.environ.get("HARNESS_SYNTHETIC_VALIDATION_FAIL") == "1":
            return {"exit_code": 1, "stdout": "", "stderr": "Synthetic validation failure"}
        if os.environ.get("HARNESS_MODE") == "H2_SYNTHETIC_E2E":
            return {"exit_code": 0, "stdout": "Synthetic validation passed", "stderr": ""}
        try:
            res = subprocess.run(cmd, cwd=cwd or self.cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e)
            }
