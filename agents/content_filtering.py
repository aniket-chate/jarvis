"""Content Filtering Module for JARVIS Layer 3 (Group 4).

Scans and filters output text before reaching Layer 1's output channels.
Rejects harmful, dangerous, or credential-leaking content.
"""

import re
import logging
from typing import Tuple, Optional

from config.settings import settings

logger = logging.getLogger("JARVIS.Safety.ContentFilter")

UNSAFE_PATTERNS = [
    (r"\b(password|secret|api_key|token)\s*=\s*['\"][a-zA-Z0-9_\-]{8,}['\"]", "Credential / secret leakage attempt"),
    (r"\b(rm\s+-rf\s+/|format\s+[c-zC-Z]:)", "Malicious OS destruction command"),
    (r"\b(powershell\s+-enc|cmd\s+/c\s+powershell)", "Obfuscated shell execution"),
    (r"\b(how\s+to\s+make\s+a\s+(bomb|explosive|malware|virus))", "Dangerous weapons or malware generation request"),
]


class ContentFilter:
    """Validates generated outputs for safety before rendering."""

    def filter_output(self, text: str, persona: Optional[str] = None) -> Tuple[bool, str, str]:
        """Scans text for unsafe patterns.

        Returns (is_safe, filtered_or_original_text, reason).
        """
        p_name = persona or settings.active_persona_name

        for pattern, reason in UNSAFE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.critical("[ContentFilter BLOCKED] [%s] Unsafe output intercepted: %s", p_name, reason)
                safe_notice = f"[Safety Filter Alert]: The generated response was blocked because it contained unsafe material ({reason})."
                return False, safe_notice, reason

        logger.debug("[ContentFilter PASS] [%s] Output verified safe", p_name)
        return True, text, "Content safe."


content_filter = ContentFilter()
