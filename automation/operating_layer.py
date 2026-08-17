import os
import json
import subprocess
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from .project_config import ProjectConfig
from .runtime_state import RuntimeStateManager

class OperatingMode(str, Enum):
    DISCUSSION = "DISCUSSION"
    SPEC = "SPEC"
    EXECUTE = "EXECUTE"

class FreshnessState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"

class ProjectOperatingLayer:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.runtime_mgr = RuntimeStateManager(root_dir)
        
    def _get_git_info(self, project_root: str) -> Dict[str, str]:
        info = {"branch": "UNKNOWN", "head": "UNKNOWN", "status": "UNKNOWN"}
        try:
            branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=project_root, text=True, stderr=subprocess.DEVNULL).strip()
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_root, text=True, stderr=subprocess.DEVNULL).strip()
            status = subprocess.check_output(["git", "status", "--short"], cwd=project_root, text=True, stderr=subprocess.DEVNULL).strip()
            info["branch"] = branch
            info["head"] = head
            info["status"] = status
        except Exception:
            pass
        return info

    def check_freshness(self, project: ProjectConfig) -> FreshnessState:
        project_root = project.resolve_root(os.path.join(self.root_dir, "projects"))
        git_info = self._get_git_info(project_root)
        
        # If there are uncommitted changes in freshness sources -> CONFLICT
        for source in project.operating_layer.freshness_sources:
            if source.replace('\\', '/') in git_info["status"].replace('\\', '/'):
                return FreshnessState.CONFLICT
                
        # Check if there's a recently completed task that's newer than the docs
        try:
            audit_dir = Path(self.root_dir) / "automation" / "runtime" / "audit"
            if not audit_dir.exists():
                return FreshnessState.FRESH
                
            latest_task_time = 0
            for task_dir in audit_dir.iterdir():
                if task_dir.is_dir() and (task_dir / "index.json").exists():
                    task_time = task_dir.stat().st_mtime
                    if task_time > latest_task_time:
                        latest_task_time = task_time
            
            if latest_task_time == 0:
                return FreshnessState.FRESH
                
            oldest_doc_commit_time = float('inf')
            for source in project.operating_layer.freshness_sources:
                doc_path = Path(project_root) / source
                if doc_path.exists():
                    try:
                        # Use git commit time instead of mtime to prevent false-pass on simple file touch
                        commit_time_str = subprocess.check_output(
                            ["git", "log", "-1", "--format=%ct", "--", source],
                            cwd=project_root, text=True, stderr=subprocess.DEVNULL
                        ).strip()
                        if commit_time_str:
                            doc_time = float(commit_time_str)
                            if doc_time < oldest_doc_commit_time:
                                oldest_doc_commit_time = doc_time
                        else:
                            # Not tracked in git? Fallback to UNKNOWN
                            return FreshnessState.UNKNOWN
                    except Exception:
                        return FreshnessState.UNKNOWN
            
            # Allow 60 seconds drift in case the task itself committed the document just before finishing
            if oldest_doc_commit_time < latest_task_time - 60.0:
                return FreshnessState.STALE
                
        except Exception:
            return FreshnessState.UNKNOWN
            
        return FreshnessState.FRESH

    def bootstrap(self, project: ProjectConfig) -> str:
        project_root = project.resolve_root(os.path.join(self.root_dir, "projects"))
        git_info = self._get_git_info(project_root)
        
        queued = self.runtime_mgr.get_queued_tasks()
        active = self.runtime_mgr.load_state()
        
        from .approval_gate import ApprovalManager
        app_mgr = ApprovalManager(self.root_dir)
        pending_apps = []
        if active:
            apps = app_mgr.get_task_approvals(active.task_id)
            pending_apps = [a.approval_id for a in apps if a.status.value == "PENDING"]
            
        freshness = self.check_freshness(project)
        
        lines = [
            f"=== BOOTSTRAP: {project.project_name} ===",
            f"Project ID: {project.project_id}",
            f"Git Branch: {git_info['branch']}",
            f"Git HEAD: {git_info['head']}",
            f"Git Status: {'CLEAN' if not git_info['status'] else 'MODIFIED'}",
            f"Freshness: {freshness.value}",
            "",
            "=== HARNESS REALITY ===",
            f"Queued Tasks: {len(queued)}",
            f"Active Task: {active.task_id if active else 'NONE'}",
            f"Pending Approvals: {', '.join(pending_apps) if pending_apps else 'NONE'}",
            "",
            "=== INSTRUCTIONS ===",
            "1. Read the provided Context Sources, Status Sources, and Rule Sources.",
            "2. Switch to DISCUSSION mode to talk with the user.",
            "3. Switch to SPEC mode to write an implementation instruction.",
            "4. Only trigger EXECUTE (via python -m automation.control create) if user explicitly confirms."
        ]
        
        return "\n".join(lines)
