"""Privacy Protection Gate for JARVIS Layer 3 (Group 4).

Ensures nothing from personal_knowledge_base or Memory Manager
reaches an external API/network call unless explicitly required for that task.
Redacts personal identifiers, private secrets, and unapproved memories.
"""

import re
import logging
from typing import Dict, Any, Optional, Set, List

from config.settings import settings

logger = logging.getLogger("JARVIS.Safety.PrivacyProtection")

# Patterns for sensitive PII
EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE_REGEX = r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
API_KEY_REGEX = r"\b(?:sk-[a-zA-Z0-9]{20,}|tvly-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,})\b"


class PrivacyProtection:
    """Guards internal private data from leaking into external network queries."""

    def __init__(self):
        self._private_keys: Set[str] = {
            "password", "secret", "private_key", "ssn", "credit_card",
            "medical", "bank_account", "tavily_api_key", "brave_api_key"
        }

    def sanitize_external_query(
        self,
        query: str,
        target_service: str,
        allow_recipient_email: bool = False
    ) -> str:
        """Sanitizes outgoing query string directed towards external search/web/cloud APIs.
        
        Removes accidentally leaked API keys, credentials, and sensitive private tokens.
        """
        sanitized = query

        # Redact any discovered API keys
        sanitized = re.sub(API_KEY_REGEX, "[REDACTED_API_KEY]", sanitized)

        # Redact emails unless explicitly sending an email (communication_agent)
        if not allow_recipient_email:
            sanitized = re.sub(EMAIL_REGEX, "[REDACTED_EMAIL]", sanitized)

        # Redact phone numbers unless communicating
        if not allow_recipient_email:
            sanitized = re.sub(PHONE_REGEX, "[REDACTED_PHONE]", sanitized)

        if sanitized != query:
            logger.warning(
                "[PrivacyProtection] Redacted sensitive PII from outbound query to %s",
                target_service
            )

        return sanitized

    def filter_memory_context_for_external(
        self,
        memory_data: Dict[str, Any],
        required_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Filters Memory Manager / PKB context before passing to external agent calls.
        
        Only passes keys that are explicitly required for the external task.
        """
        if not memory_data:
            return {}

        required_set = set(required_keys or [])
        safe_context: Dict[str, Any] = {}

        for k, v in memory_data.items():
            if k in self._private_keys:
                logger.warning("[PrivacyProtection] Suppressed highly sensitive key '%s' from external call", k)
                continue
            if required_keys is None or k in required_set:
                safe_context[k] = v
            else:
                logger.debug("[PrivacyProtection] Omitted non-essential memory key '%s'", k)

        return safe_context


privacy_protection = PrivacyProtection()
