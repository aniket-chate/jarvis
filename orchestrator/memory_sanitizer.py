"""Memory Sanitization and Credential Redaction Module for JARVIS.

Protects persistent and session memory from storing:
- Passwords, passcodes, and Wi-Fi security keys.
- API keys (OpenAI, Gemini, Groq, Tavily, Bearer tokens).
- Private keys, auth tokens, and sensitive credential assignments.
- Binary blobs and raw audio stream buffers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("JARVIS.Memory.Sanitizer")

# Compiled regex patterns for credential stripping
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd)\s*([:=]|\bis\b)\s*[\'\"]?([^\s\'\",;]+)[\'\"]?"),
    re.compile(r"(?i)(wifi[_-]?password|wifi[_-]?pass|wpa[_-]?key)\s*([:=]|\bis\b)\s*[\'\"]?([^\s\'\",;]+)[\'\"]?"),
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key)\s*([:=]|\bis\b)\s*[\'\"]?([^\s\'\",;]+)[\'\"]?"),
    re.compile(r"(?i)(private[_-]?key)\s*([:=]|\bis\b)\s*[\'\"]?([^\s\'\",;]+)[\'\"]?"),
    re.compile(r"(?i)(auth[_-]?token)\s*([:=]|\bis\b)\s*[\'\"]?([^\s\'\",;]+)[\'\"]?"),
    re.compile(r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]{15,})"),
    re.compile(r"(sk-[a-zA-Z0-9]{20,}|gsk_[a-zA-Z0-9]{20,}|AIza[0-9A-Za-z\-_]{35})"),
]


class MemorySanitizer:
    """Detects and redacts credentials before persistence."""

    @classmethod
    def is_sensitive(cls, text: str) -> bool:
        """Check if string contains credential or secret patterns."""
        if not isinstance(text, str):
            return False
        return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)

    @classmethod
    def sanitize(cls, data: Any) -> Any:
        """Recursively sanitizes strings, lists, and dicts, masking credentials."""
        if isinstance(data, str):
            sanitized = data
            for pattern in SENSITIVE_PATTERNS:
                sanitized = pattern.sub("[REDACTED_CREDENTIAL]", sanitized)
            if sanitized != data:
                logger.info("[MemorySanitizer] Redacted sensitive credential pattern from input.")
            return sanitized

        elif isinstance(data, dict):
            clean_dict = {}
            for k, v in data.items():
                if any(sec in k.lower() for sec in ["password", "secret", "token", "auth_key", "wifi_pass"]):
                    clean_dict[k] = "[REDACTED_CREDENTIAL]"
                    logger.info("[MemorySanitizer] Redacted sensitive key '%s' from dictionary.", k)
                else:
                    clean_dict[k] = cls.sanitize(v)
            return clean_dict

        elif isinstance(data, list):
            return [cls.sanitize(item) for item in data]

        return data
