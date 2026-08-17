import os
from .base import BaseAdapter
from ..models import CommandSpec
from ..config import PROJECT_ROOT

class CodexAdapter(BaseAdapter):
    def build_command(self, prompt: str) -> CommandSpec:
        pass # Not used directly

    def build_plan_command(self, prompt: str) -> CommandSpec:
        schema_path = os.path.join(PROJECT_ROOT, "automation", "schemas", "senior_plan.schema.json")
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
            
        return CommandSpec(
            executable="codex",
            args=[
                "exec",
                "-c", "windows.sandbox=\"unelevated\"",
                "--sandbox", "read-only",
                "--output-schema", schema_path,
                prompt
            ],
            cwd=PROJECT_ROOT,
            safe_mode=True
        )

    def build_review_command(self, prompt: str) -> CommandSpec:
        schema_path = os.path.join(PROJECT_ROOT, "automation", "schemas", "review_result.schema.json")
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
            
        return CommandSpec(
            executable="codex",
            args=[
                "exec",
                "-c", "windows.sandbox=\"unelevated\"",
                "--sandbox", "read-only",
                "--output-schema", schema_path,
                prompt
            ],
            cwd=PROJECT_ROOT,
            safe_mode=True
        )
