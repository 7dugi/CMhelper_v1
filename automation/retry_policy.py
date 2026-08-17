from enum import Enum
from .provider_status import ProviderStatus, ProviderEvent

class RetryAction(str, Enum):
    RETRY_IMMEDIATELY = "RETRY_IMMEDIATELY"
    WAIT_FOR_QUOTA = "WAIT_FOR_QUOTA"
    USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"
    NON_RETRYABLE = "NON_RETRYABLE"

class RetryPolicy:
    MAX_TRANSIENT_RETRIES = 3

    @classmethod
    def determine_action(cls, event: ProviderEvent, attempt_count: int) -> RetryAction:
        if event.status == ProviderStatus.QUOTA_EXHAUSTED:
            return RetryAction.WAIT_FOR_QUOTA
            
        if event.status == ProviderStatus.RATE_LIMITED:
            if attempt_count < cls.MAX_TRANSIENT_RETRIES:
                return RetryAction.RETRY_IMMEDIATELY
            return RetryAction.WAIT_FOR_QUOTA
            
        if event.status in [ProviderStatus.AUTH_FAILED, ProviderStatus.AUTH_REQUIRED]:
            return RetryAction.USER_ACTION_REQUIRED
            
        if event.status in [ProviderStatus.TEMPORARILY_UNAVAILABLE, ProviderStatus.UNKNOWN_ERROR]:
            if attempt_count < cls.MAX_TRANSIENT_RETRIES:
                return RetryAction.RETRY_IMMEDIATELY
            return RetryAction.NON_RETRYABLE

        if event.status == ProviderStatus.AVAILABLE:
            # Should not happen, but just in case
            return RetryAction.NON_RETRYABLE
            
        return RetryAction.NON_RETRYABLE
