from typing import Optional
from ..models import CommandSpec
from ..config import DRY_RUN

class BaseAdapter:
    def build_command(self, prompt: str) -> CommandSpec:
        raise NotImplementedError

    def execute(self, cmd: CommandSpec) -> Optional[str]:
        if DRY_RUN:
            return None
        # Subprocess logic here in H2
        raise NotImplementedError
