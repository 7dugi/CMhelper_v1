import os
import json
import tempfile
import subprocess
from typing import Dict, Any
from pathlib import Path
from .models import NextTaskResolution, NextTaskCandidate
from .config import PROJECT_ROOT

class NextTaskResolver:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.schema_path = os.path.join(self.root_dir, "automation", "schemas", "next_task_resolution.schema.json")
        
    def resolve(self, bundle: Dict[str, Any]) -> NextTaskResolution:
        # We will use codex to resolve the next task based on the context bundle
        prompt = f"""You are the Next Task Resolver for CMhelper Harness.
Analyze the following project context bundle and determine the next development task.

Context:
Project ID: {bundle.get('project_id')}
Phase Info: {bundle.get('phase_info', '')}

Documents:
"""
        for doc_name, content in bundle.get("documents", {}).items():
            prompt += f"\n--- {doc_name} ---\n{content}\n"
            
        prompt += """
Rules for Next Task Resolution:
1. Check CURRENT_STATUS.md for completed tasks.
2. Check ROADMAP.md for the next incomplete task.
3. Use TODO.md for priority.
4. Check TECHNICAL_PRINCIPLES.md for constraints.
5. If there is ONE clear, safe task to do next: return READY with confidence HIGH.
6. If there are multiple equal choices, architecture decisions, or high-risk tasks: return NEED_USER_DECISION.
7. If dependencies are missing or blocked: return BLOCKED.
8. NEVER skip roadmap items arbitrarily.

Output a valid JSON matching the schema.
"""
        try:
            cmd = [
                "codex", "exec", 
                "--sandbox", "read-only",
                "-c", "windows.sandbox=\"unelevated\"",
                "--output-schema", self.schema_path
            ]
            
            # Using Popen to write to stdin to bypass command line length limits
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.root_dir, encoding='utf-8')
            stdout, stderr = process.communicate(input=prompt)
            
            if process.returncode == 0 and stdout.strip():
                try:
                    data = json.loads(stdout.strip())
                    return NextTaskResolution(**data)
                except Exception as e:
                    return NextTaskResolution(
                        project_id=bundle.get('project_id', 'unknown'),
                        result="BLOCKED",
                        reason=f"Failed to parse Codex response: {e}"
                    )
            else:
                return NextTaskResolution(
                    project_id=bundle.get('project_id', 'unknown'),
                    result="BLOCKED",
                    reason=f"Codex execution failed: {stderr}"
                )
        except Exception as e:
            return NextTaskResolution(
                project_id=bundle.get('project_id', 'unknown'),
                result="BLOCKED",
                reason=f"Exception during Codex execution: {e}"
            )
