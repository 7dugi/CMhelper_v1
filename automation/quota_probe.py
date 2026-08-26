from .provider_status import ProviderStatus, ProviderEvent
from .quota_detector import QuotaDetector
from .cli_runner import CLIRunner
from .adapters.antigravity_adapter import AntigravityAdapter
from .adapters.codex_adapter import CodexAdapter

class ProviderHealthChecker:
    def __init__(self):
        self.runner = CLIRunner()
        self.agy = AntigravityAdapter()
        self.codex = CodexAdapter()

    def check(self, provider: str) -> ProviderEvent:
        if provider == "antigravity":
            # 1. Native API check (Not available in current AGY CLI)
            # 2. Fallback to tiny read-only prompt
            # Use smallest possible prompt, no files, no MCP
            prompt = "Return 'OK'. Do nothing else."
            cmd = self.agy.build_command(prompt)
            # Disable safe mode to just run purely read-only text (if applicable, but build_command does default)
            res = self.runner.run(cmd)
            return QuotaDetector.classify_provider_failure(provider, res.get("stdout", ""), res.get("stderr", ""), res.get("exit_code", 1))
            
        elif provider == "codex":
            prompt = "Return 'OK'. Do nothing else."
            cmd = self.codex.build_plan_command(prompt)
            res = self.runner.run(cmd)
            return QuotaDetector.classify_provider_failure(provider, res.get("stdout", ""), res.get("stderr", ""), res.get("exit_code", 1))
            
        return ProviderEvent(provider=provider, status=ProviderStatus.AVAILABLE)
