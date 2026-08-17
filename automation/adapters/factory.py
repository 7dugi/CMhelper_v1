from .base import BaseAdapter
from .codex_adapter import CodexAdapter
from .antigravity_adapter import AntigravityAdapter

class ProviderFactory:
    @staticmethod
    def get_adapter(provider_name: str) -> BaseAdapter:
        if provider_name == "codex":
            return CodexAdapter()
        elif provider_name == "antigravity":
            return AntigravityAdapter()
        elif provider_name == "disabled":
            raise ValueError(f"Provider '{provider_name}' is disabled.")
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")
