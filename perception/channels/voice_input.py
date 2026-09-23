"""Voice Input Channel for JARVIS.

Captures 16kHz mono audio streams or recorded audio buffers,
with graceful degradation if microphone hardware is absent or busy.
"""

import logging
from typing import Optional, Dict, Any
import numpy as np
import sounddevice as sd

from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Channels.Voice")

DEFAULT_SAMPLE_RATE = 16000  # 16kHz required by Whisper and openWakeWord


class VoiceInputChannel:
    """Channel for capturing raw audio buffers and microphone clips."""

    def __init__(self, sample_rate: int = DEFAULT_SAMPLE_RATE):
        self.sample_rate = sample_rate

    def is_microphone_available(self) -> bool:
        """Checks whether an audio input device is available."""
        try:
            devices = sd.query_devices()
            input_devs = [d for d in devices if d.get("max_input_channels", 0) > 0]
            return len(input_devs) > 0
        except Exception as e:
            logger.warning("[VoiceInputChannel] Could not query audio devices: %s", str(e))
            return False

    def record_clip(self, duration_seconds: float = 3.0) -> Optional[np.ndarray]:
        """Records an audio clip from the default input device (CPU only)."""
        if not self.is_microphone_available():
            logger.warning("[VoiceInputChannel] No microphone available. Degrading gracefully.")
            return None

        try:
            num_samples = int(duration_seconds * self.sample_rate)
            logger.info("[VoiceInputChannel] Recording %.1fs clip at %d Hz...", duration_seconds, self.sample_rate)
            audio = sd.rec(num_samples, samplerate=self.sample_rate, channels=1, dtype="int16")
            sd.wait()
            return audio.flatten()
        except Exception as e:
            logger.error("[VoiceInputChannel Recording Error] %s", str(e))
            return None

    def ingest_buffer(self, audio_data: np.ndarray, samplerate: int = DEFAULT_SAMPLE_RATE) -> PerceptionEvent:
        """Ingests an in-memory audio array and emits a voice_input event."""
        num_samples = len(audio_data)
        duration_s = round(num_samples / samplerate, 2)
        payload = {
            "sample_rate": samplerate,
            "samples_count": num_samples,
            "duration_seconds": duration_s,
            "max_amplitude": int(np.max(np.abs(audio_data))) if num_samples > 0 else 0,
            "audio_data": audio_data,
        }

        event = PerceptionEvent(
            type="voice_input",
            payload=payload,
            source="voice_input",
            active_persona=settings.active_persona_name,
        )

        logger.debug("[VoiceInputChannel] Ingested audio buffer: %d samples (%.2fs)", num_samples, duration_s)
        event_bus.publish(event)
        return event


voice_input_channel = VoiceInputChannel()
