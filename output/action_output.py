"""Action Output Channel for JARVIS (Log-only stub).

Records and logs system actions, tool invocations, and hardware control events.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger("JARVIS.Output.Action")


class ActionOutputChannel:
    """Channel for logging action dispatches without executing arbitrary mutations."""

    def __init__(self):
        self._action_history = []

    def dispatch(self, action_name: str, parameters: Dict[str, Any], persona_name: Optional[str] = None) -> Dict[str, Any]:
        """Logs action dispatch event."""
        persona = persona_name or settings.active_persona_name
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action_name,
            "parameters": parameters,
            "persona": persona,
            "status": "logged",
        }
        self._action_history.append(record)
        logger.info("[ActionOutput Log] Persona '%s' dispatched action '%s': %s", persona, action_name, parameters)
        return record

    def get_history(self):
        return self._action_history


action_output = ActionOutputChannel()
