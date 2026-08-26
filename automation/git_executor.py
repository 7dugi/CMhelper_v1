import subprocess
from typing import List, Tuple, Optional
from pathlib import Path
import os
from .models import ReviewStatus, ValidationResult

class GitExecutionError(Exception):
    pass

class SafeGitExecutor:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def _run_git(self, args: List[str]) -> Tuple[str, str, int]:
        cmd = ["git"] + args
        res = subprocess.run(cmd, cwd=self.root_dir, capture_output=True, text=True)
        return res.stdout, res.stderr, res.returncode

    def status(self) -> str:
        out, err, code = self._run_git(["status", "--short"])
        if code != 0:
            raise GitExecutionError(f"Git status failed: {err}")
        return out.strip()

    def diff(self) -> str:
        out, err, code = self._run_git(["diff"])
        return out

    def get_current_branch(self) -> str:
        out, err, code = self._run_git(["branch", "--show-current"])
        if code != 0:
            raise GitExecutionError(f"Failed to get branch: {err}")
        return out.strip()

    def check_commit_gate(
        self,
        approval_status: str,
        review_status: ReviewStatus,
        validation_tests_status: str,
        validation_build_status: str,
        mutation_guard_pass: bool,
        permission_cleanup_pass: bool,
        expected_branch: str,
        allowed_mutation_paths: List[str]
    ) -> bool:
        """
        Commit Gate conditions. Returns True if ALL conditions are met.
        """
        if approval_status != "APPROVED":
            return False
        if review_status != ReviewStatus.PASS:
            return False
        if validation_tests_status != "PASS" or validation_build_status != "PASS":
            return False
        if not mutation_guard_pass:
            return False
        if not permission_cleanup_pass:
            return False
            
        current_branch = self.get_current_branch()
        if current_branch != expected_branch:
            return False

        # Check if changed files are within allowed_mutation_paths
        status_lines = self.status().splitlines()
        for line in status_lines:
            if not line:
                continue
            # Format: ' M path' or '?? path'
            file_path = line[2:].strip()
            # Must be in allowed paths
            is_allowed = False
            # Quick check - strictly exact or within directory if we allowed that
            # For Harness H3/H4, we assume allowed_mutation_paths are exact file paths
            # OR we allow automation/ runtime files explicitly
            if file_path in allowed_mutation_paths:
                is_allowed = True
            elif file_path.startswith("automation/runtime/"):
                is_allowed = True
                
            if not is_allowed:
                return False
                
        return True

    def commit(self, allowed_files: List[str], message: str) -> str:
        """
        Safely adds allowed_files and commits.
        Returns the Commit SHA.
        """
        # 1. Add only allowed files
        for f in allowed_files:
            out, err, code = self._run_git(["add", f])
            if code != 0:
                raise GitExecutionError(f"Failed to add {f}: {err}")
                
        # Also add runtime files safely
        self._run_git(["add", "automation/runtime/"])
                
        # 2. Commit
        out, err, code = self._run_git(["commit", "-m", message])
        if code != 0:
            if "nothing to commit" in out or "nothing to commit" in err:
                return self._run_git(["rev-parse", "HEAD"])[0].strip()
            raise GitExecutionError(f"Commit failed: {err}")
            
        # 3. Get SHA
        sha, err, code = self._run_git(["rev-parse", "HEAD"])
        return sha.strip()
        
    def push(self, remote: str = "origin") -> bool:
        """
        Safely push the current branch.
        """
        branch = self.get_current_branch()
        out, err, code = self._run_git(["push", remote, branch])
        if code != 0:
            raise GitExecutionError(f"Push failed: {err}")
        return True
