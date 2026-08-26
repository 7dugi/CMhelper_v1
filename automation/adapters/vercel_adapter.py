import os
import json
import subprocess
from typing import Optional, List
from ..models import VercelResult, VercelAccessMode

class VercelAdapterError(Exception):
    pass

class VercelAdapter:
    def __init__(self, root_dir: str = ".", mode: VercelAccessMode = VercelAccessMode.READ_ONLY):
        self.root_dir = root_dir
        self.mode = mode
        self.is_linked = self._check_linked()

    def _check_linked(self) -> bool:
        project_json_path = os.path.join(self.root_dir, ".vercel", "project.json")
        return os.path.exists(project_json_path)

    def _run_cli(self, args: List[str]) -> str:
        # Assuming vercel is installed globally or accessible via npx
        cmd = ["vercel"] + args
        try:
            # We use shell=True on Windows because 'vercel' is a .cmd or .ps1
            result = subprocess.run(
                cmd, 
                cwd=self.root_dir, 
                capture_output=True, 
                text=True, 
                shell=True
            )
            if result.returncode != 0:
                raise VercelAdapterError(f"Vercel CLI error: {result.stderr.strip()}")
            return result.stdout
        except FileNotFoundError:
            # Fallback to npx vercel
            cmd = ["npx", "vercel"] + args
            result = subprocess.run(
                cmd, 
                cwd=self.root_dir, 
                capture_output=True, 
                text=True, 
                shell=True
            )
            if result.returncode != 0:
                raise VercelAdapterError(f"Vercel CLI error: {result.stderr.strip()}")
            return result.stdout

    def get_latest_preview(self) -> VercelResult:
        """Gets the latest preview deployment for the current branch/project."""
        if not self.is_linked:
            raise VercelAdapterError("Project is not linked to Vercel.")
            
        try:
            # `vercel ls --yes --json`
            stdout = self._run_cli(["ls", "--yes", "--json"])
            # Vercel CLI might output some text before JSON, but usually --json is clean.
            # We'll try to find the JSON array/object.
            
            # Find first { or [
            start_idx = -1
            for i, char in enumerate(stdout):
                if char in ('{', '['):
                    start_idx = i
                    break
                    
            if start_idx == -1:
                raise ValueError("No JSON found in output")
                
            json_str = stdout[start_idx:]
            data = json.loads(json_str)
            
            # Some versions of vercel return a list, some return an object with deployments
            deployments = data if isinstance(data, list) else data.get("deployments", [])
            
            if not deployments:
                return VercelResult(status="NOT_FOUND", error_reason="No deployments found")
                
            # Filter for latest preview
            # We just take the first one since ls is sorted by latest
            latest = deployments[0]
            
            url = latest.get("url")
            if url and not url.startswith("http"):
                url = f"https://{url}"
                
            status = latest.get("state", "UNKNOWN")
            
            return VercelResult(
                deployment_id=latest.get("uid"),
                url=url,
                status=status,
                created_at=latest.get("created"),
                error_reason=latest.get("error"),
                is_production=(latest.get("target") == "production")
            )
            
        except Exception as e:
            return VercelResult(status="ERROR", error_reason=str(e))

    def trigger_preview_deploy(self) -> VercelResult:
        if self.mode != VercelAccessMode.PREVIEW_DEPLOY:
            raise VercelAdapterError("Cannot trigger deploy in READ_ONLY mode.")
        
        if not self.is_linked:
            raise VercelAdapterError("Project is not linked to Vercel.")
            
        try:
            # Note: Production deploy uses --prod, we omit it for preview.
            stdout = self._run_cli(["--yes", "--json"])
            # Parse output
            # Output of `vercel --json` is a JSON object about the new deployment
            start_idx = -1
            for i, char in enumerate(stdout):
                if char == '{':
                    start_idx = i
                    break
            
            if start_idx == -1:
                # Sometimes `vercel` returns just the URL if not JSON, but --json should return JSON
                return VercelResult(status="UNKNOWN", error_reason="No JSON found, raw: " + stdout.strip())
                
            json_str = stdout[start_idx:]
            data = json.loads(json_str)
            
            url = data.get("url")
            if url and not url.startswith("http"):
                url = f"https://{url}"
                
            return VercelResult(
                deployment_id=data.get("id") or data.get("uid"),
                url=url,
                status="BUILDING",
                created_at=data.get("createdAt"),
            )
        except Exception as e:
            return VercelResult(status="ERROR", error_reason=str(e))
