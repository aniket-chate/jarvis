"""Voice Output Channel for JARVIS.

Routes text synthesis to local Piper neural TTS running strictly on CPU,
selecting persona-specific voices with graceful fallback.
Zero VRAM consumption.
"""

import logging
from typing import Optional
from voice.tts_piper import tts_engine
from config.settings import settings

logger = logging.getLogger("JARVIS.Output.Voice")


class VoiceOutputChannel:
    """Channel for dispatching neural speech synthesis."""

    def speak(self, text: str, persona_name: Optional[str] = None) -> None:
        """Synthesizes and speaks text using the persona's voice."""
        persona = persona_name or settings.active_persona_name
        logger.info("[VoiceOutput] Speaking as %s: '%s'", persona, text[:40])
        tts_engine.speak(text, persona_name=persona)


voice_output = VoiceOutputChannel()
