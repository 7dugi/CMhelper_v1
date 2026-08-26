import os
import subprocess
import time
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple
from .models import CommandSpec
from .config import PROJECT_ROOT
import automation.config as config

class CLIRunner:
    def __init__(self):
        self.allowed_executables = {"codex", "agy"}
        self.mock_bin_dir = os.path.join(PROJECT_ROOT, "automation", "mock_bin")

    def resolve_executable(self, provider: str) -> Tuple[Path, str]:
        if provider not in self.allowed_executables:
            raise ValueError(f"Provider {provider} not in allowlist.")
        
        env_var = f"{provider.upper()}_EXECUTABLE"
        
        env_path = os.environ.get(env_var)
        if env_path:
            p = Path(env_path)
            if p.is_file() and p.suffix.lower() == ".exe":
                return p, "env"
        
        which_path = shutil.which(provider)
        if which_path:
            p = Path(which_path)
            if p.is_file() and p.suffix.lower() == ".exe":
                return p, "path"
                
        if provider == "codex":
            p = Path.home() / "AppData" / "Local" / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe"
        elif provider == "agy":
            p = Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy.exe"
            
        if p.is_file() and p.suffix.lower() == ".exe":
            return p, "default_location"
            
        raise FileNotFoundError(f"Could not resolve actual executable for provider: {provider}")

    def run(self, cmd: CommandSpec, timeout: int = 300) -> Dict[str, Any]:
        if config.HARNESS_MODE not in ["H2_READ_ONLY", "H2_REAL_READ_ONLY"]:
            raise RuntimeError(f"CLI Execution is not permitted in mode: {config.HARNESS_MODE}")

        if cmd.executable not in self.allowed_executables:
            raise ValueError(f"Executable {cmd.executable} is not allowed.")

        if os.path.abspath(cmd.cwd) != os.path.abspath(PROJECT_ROOT):
            raise ValueError(f"CWD must be PROJECT_ROOT. Got: {cmd.cwd}")

        env = os.environ.copy()
        
        resolved_path, res_source = self.resolve_executable(cmd.executable)
        
        mock_used = False
        if config.HARNESS_MODE == "H2_READ_ONLY":
            if os.path.exists(self.mock_bin_dir):
                env["PATH"] = f"{self.mock_bin_dir};{env.get('PATH', '')}"
                mock_used = True
        elif config.HARNESS_MODE == "H2_REAL_READ_ONLY":
            pass

        start_time = time.time()
        
        # Determine appropriate timeout from config if not overridden
        actual_timeout = timeout
        if cmd.executable == "codex":
            if "Review input:" in " ".join(cmd.args):
                actual_timeout = config.CODEX_REVIEW_TIMEOUT_SECONDS
            else:
                actual_timeout = config.CODEX_PLAN_TIMEOUT_SECONDS
        elif cmd.executable == "agy":
            actual_timeout = config.ANTIGRAVITY_TIMEOUT_SECONDS

        timed_out = False
        
        try:
            result = subprocess.run(
                [str(resolved_path)] + cmd.args,
                cwd=cmd.cwd,
                env=env,
                capture_output=True,
                text=True,
                shell=False,
                timeout=actual_timeout,
                encoding='utf-8',
                errors='replace',
                stdin=subprocess.DEVNULL
            )
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired as e:
            exit_code = -1
            stdout = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode('utf-8', 'replace') if e.stdout else "")
            stderr = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode('utf-8', 'replace') if e.stderr else f"TIMEOUT after {actual_timeout}s")
            timed_out = True
        except Exception as e:
            exit_code = -1
            stdout = ""
            stderr = str(e)
            
        duration_ms = int((time.time() - start_time) * 1000)

        safe_args = []
        for arg in cmd.args:
            if "TOKEN" in arg or "WEBHOOK" in arg:
                safe_args.append("***")
            else:
                safe_args.append(arg)

        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
            "command_summary": f"{cmd.executable} {' '.join(safe_args)}",
            "resolved_path": str(resolved_path),
            "resolution_source": res_source,
            "mock_used": mock_used,
            "timed_out": timed_out
        }
