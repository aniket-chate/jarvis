"""Multi-Persona Event Listener for JARVIS Layer 1.

Simultaneously monitors wake words for all 4 personas:
- Jarvis (jarvis.onnx)
- Friday (friday.onnx)
- Ultron (ultron.onnx)
- Omi (omi.onnx)

Whichever wake word triggers sets `active_persona` for the session and emits a
'wake_word_trigger' PerceptionEvent, followed immediately by a 'face_capture' event.
"""

import logging
from typing import Dict, Any, Optional
import numpy as np

from config.settings import settings
from perception.events import PerceptionEvent, event_bus
from perception.identity_capture import identity_capture
from wakeword.engine import MultiPersonaWakeWordEngine

logger = logging.getLogger("JARVIS.EventListener")


class MultiPersonaEventListener:
    """Orchestrates simultaneous 4-persona wake detection and identity capture."""

    def __init__(self):
        self.wakeword_engine = MultiPersonaWakeWordEngine()
        self.personas = ["Jarvis", "Friday", "Ultron", "Omi"]

    def trigger_persona(self, persona_name: str, score: float = 0.98, capture_face: bool = True) -> Dict[str, Any]:
        """Manually or programmatically triggers a wake word for a persona.

        Sets active_persona, emits wake_word_trigger PerceptionEvent,
        and optionally grabs a face-embedding frame.
        """
        # Normalize and match persona
        target_name = None
        for p in self.personas:
            if p.lower() == persona_name.lower():
                target_name = p
                break

        if not target_name:
            logger.warning("[EventListener] Unknown persona trigger attempted: '%s'", persona_name)
            return {"success": False, "error": f"Unknown persona '{persona_name}'"}

        # 1. Update active persona
        settings.set_active_persona(target_name)
        active_persona = settings.active_persona_name

        # 2. Emit wake_word_trigger PerceptionEvent
        payload: Dict[str, Any] = {
            "triggered_persona": active_persona,
            "wake_model": f"{active_persona.lower()}.onnx",
            "score": score,
            "tone": settings.get_persona(active_persona).tone,
            "voice": settings.get_persona(active_persona).voice,
        }

        wake_event = PerceptionEvent(
            type="wake_word_trigger",
            payload=payload,
            source="event_listener",
            active_persona=active_persona,
        )
        logger.info("[EventListener] WAKE WORD FIRED: '%s' -> Set active_persona='%s'", target_name, active_persona)
        event_bus.publish(wake_event)

        # 3. Identity Capture (grabs face frame on any wake-word trigger)
        face_event = None
        if capture_face:
            face_event = identity_capture.capture_and_embed()

        return {
            "success": True,
            "active_persona": active_persona,
            "wake_event": wake_event,
            "face_event": face_event,
        }

    def process_audio_chunk(self, audio_chunk: np.ndarray) -> Optional[PerceptionEvent]:
        """Processes an incoming PCM audio frame through openWakeWord."""
        res = self.wakeword_engine.process_audio_frame(audio_chunk)
        if res:
            persona_name, score = res
            result = self.trigger_persona(persona_name, score=score)
            return result.get("wake_event")
        return None

    def process_spoken_wake_phrase(self, phrase: str) -> Optional[Dict[str, Any]]:
        """Acoustic / keyword parser recognizing any of the 4 wake words in text."""
        p_lower = phrase.lower()
        for persona in self.personas:
            if persona.lower() in p_lower:
                return self.trigger_persona(persona, score=0.99)
        return None


event_listener = MultiPersonaEventListener()
