from .base import BaseAdapter
from ..models import CommandSpec
from ..config import PROJECT_ROOT

class CodexAdapter(BaseAdapter):
    def build_command(self, prompt: str) -> CommandSpec:
        pass # Not used directly

    def build_plan_command(self, prompt: str) -> CommandSpec:
        return CommandSpec(
            executable="codex",
            args=[
                "exec",
                "-c", "windows.sandbox=\"unelevated\"",
                "--sandbox", "read-only",
                "-p", prompt
            ],
            cwd=PROJECT_ROOT,
            safe_mode=True
        )

    def build_review_command(self, prompt: str) -> CommandSpec:
        return CommandSpec(
            executable="codex",
            args=[
                "exec",
                "-c", "windows.sandbox=\"unelevated\"",
                "--sandbox", "read-only",
                "-p", prompt
            ],
            cwd=PROJECT_ROOT,
            safe_mode=True
        )
