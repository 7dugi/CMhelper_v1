import re
from typing import Optional
from .provider_status import ProviderStatus, ProviderEvent

class QuotaDetector:
    QUOTA_PATTERNS = [
        re.compile(r"quota\b", re.IGNORECASE),
        re.compile(r"quota reached", re.IGNORECASE),
        re.compile(r"baseline quota", re.IGNORECASE),
        re.compile(r"resource exhausted", re.IGNORECASE)
    ]
    
    RATE_LIMIT_PATTERNS = [
        re.compile(r"rate limit", re.IGNORECASE),
        re.compile(r"too many requests", re.IGNORECASE),
        re.compile(r"\b429\b")
    ]

    @classmethod
    def classify_provider_failure(cls, provider: str, stdout: str, stderr: str, exit_code: int) -> ProviderEvent:
        combined_output = f"{stdout}\n{stderr}"
        
        # 1. Check for Quota Exhaustion
        for pattern in cls.QUOTA_PATTERNS:
            if pattern.search(combined_output):
                return ProviderEvent(
                    provider=provider,
                    status=ProviderStatus.QUOTA_EXHAUSTED,
                    message=f"Quota exhausted detected via pattern: {pattern.pattern}",
                    retryable=False
                )
                
        # 2. Check for Rate Limit
        for pattern in cls.RATE_LIMIT_PATTERNS:
            if pattern.search(combined_output):
                return ProviderEvent(
                    provider=provider,
                    status=ProviderStatus.RATE_LIMITED,
                    message=f"Rate limit detected via pattern: {pattern.pattern}",
                    retryable=True
                )
                
        # 3. Check for specific API/Auth errors
        if "unauthorized" in combined_output.lower() or "authentication failed" in combined_output.lower():
            return ProviderEvent(
                provider=provider,
                status=ProviderStatus.AUTH_FAILED,
                message="Authentication failure detected",
                retryable=False
            )

        # 4. Fallback for non-zero exit codes
        if exit_code != 0:
            return ProviderEvent(
                provider=provider,
                status=ProviderStatus.UNKNOWN_ERROR,
                message=f"Process exited with code {exit_code}",
                retryable=True
            )
            
        return ProviderEvent(
            provider=provider,
            status=ProviderStatus.AVAILABLE,
            message="No failure detected",
            retryable=True
        )
