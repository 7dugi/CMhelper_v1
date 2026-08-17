import subprocess
from automation.config import PROJECT_ROOT

class EvidenceExecutor:
    """
    Harness component responsible for executing safe, pre-defined commands 
    to gather evidence, ensuring Antigravity does not run raw shell commands.
    """
    
    ALLOWED_PROFILES = {
        "tests": ["python", "-m", "unittest", "discover", "-s", "automation/tests"],
        "compileall": ["python", "-m", "compileall", "automation/"]
    }

    def __init__(self, cwd: str = PROJECT_ROOT):
        self.cwd = cwd

    def capture_repo_snapshot(self) -> str:
        """Captures git status and git diff."""
        status = self._run_git(["status", "--short"])
        diff = self._run_git(["diff", "--name-only"])
        return f"STATUS:\n{status}\nDIFF:\n{diff}"

    def capture_git_diff(self) -> str:
        """Captures detailed git diff."""
        return self._run_git(["diff"])

    def capture_changed_files(self) -> list:
        """Returns a list of changed files."""
        out = self._run_git(["diff", "--name-only"])
        return [line.strip() for line in out.splitlines() if line.strip()]

    def run_tests(self, profile: str = "tests") -> dict:
        """Runs pre-defined tests from the CMhelper Validation Profile."""
        if profile not in self.ALLOWED_PROFILES:
            raise ValueError(f"Profile {profile} is not allowed. Choose from {list(self.ALLOWED_PROFILES.keys())}")
            
        cmd = self.ALLOWED_PROFILES[profile]
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

    def _run_safe(self, cmd: list) -> dict:
        try:
            res = subprocess.run(cmd, cwd=self.cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
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
