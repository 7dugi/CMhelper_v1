import re

class SecretMasker:
    # Common secret patterns
    PATTERNS = [
        re.compile(r'(?i)(api[_-]?key[\'"]?\s*[:=]\s*[\'"]?)([a-zA-Z0-9_\-]+)([\'"]?)'),
        re.compile(r'(?i)(bearer\s+)([a-zA-Z0-9_\-\.]+)'),
        re.compile(r'(?i)(discord\.com/api/webhooks/\d+/)([a-zA-Z0-9_\-]+)'),
        re.compile(r'(?i)(password[\'"]?\s*[:=]\s*[\'"]?)([^&\'"\s]+)([\'"]?)'),
        re.compile(r'(?i)(token[\'"]?\s*[:=]\s*[\'"]?)([^&\'"\s]+)([\'"]?)')
    ]

    @classmethod
    def mask(cls, text: str) -> str:
        if not text:
            return text
            
        masked_text = text
        for pattern in cls.PATTERNS:
            def repl(match):
                prefix = match.group(1)
                secret = match.group(2)
                suffix = match.group(3) if len(match.groups()) > 2 else ""
                
                # Mask all but first and last 2 chars if length > 6
                if len(secret) > 6:
                    masked_secret = secret[:2] + "*" * (len(secret) - 4) + secret[-2:]
                else:
                    masked_secret = "***"
                    
                return f"{prefix}{masked_secret}{suffix}"
                
            masked_text = pattern.sub(repl, masked_text)
            
        return masked_text
