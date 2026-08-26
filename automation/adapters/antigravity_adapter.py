from .base import BaseAdapter
from ..models import CommandSpec
from ..config import PROJECT_ROOT

class AntigravityAdapter(BaseAdapter):
    def build_command(self, prompt: str) -> CommandSpec:
        return CommandSpec(
            executable="agy",
            args=[
                "--add-dir", PROJECT_ROOT,
                "--print",
                prompt
            ],
            cwd=PROJECT_ROOT,
            safe_mode=True
        )
