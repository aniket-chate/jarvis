"""Speech Processing Module for JARVIS Layer 1.

Processes raw audio buffers using local Whisper CPU (whisper.cpp / faster-whisper),
extracting transcription text and emitting 'speech_transcript' PerceptionEvents.
"""

import io
import wave
import logging
from typing import Dict, Any, Optional
import numpy as np

from voice.asr import asr_engine
from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Processing.Speech")


class SpeechProcessor:
    """ASR transcription processor utilizing faster-whisper on CPU."""

    def process_buffer(self, audio_data: np.ndarray, samplerate: int = 16000) -> PerceptionEvent:
        """Transcribes audio buffer and publishes a speech_transcript event."""
        transcript = asr_engine.transcribe_audio_buffer(audio_data, samplerate=samplerate)
        num_samples = len(audio_data)
        duration_s = round(num_samples / samplerate, 2)

        payload: Dict[str, Any] = {
            "transcript": transcript,
            "duration_seconds": duration_s,
            "sample_rate": samplerate,
            "has_speech": bool(transcript.strip()),
            "engine": "whisper_cpu",
        }

        event = PerceptionEvent(
            type="speech_transcript",
            payload=payload,
            source="speech_processing",
            active_persona=settings.active_persona_name,
        )

        logger.info("[SpeechProcessor] Transcribed (%.1fs): '%s'", duration_s, transcript)
        event_bus.publish(event)
        return event

    def process_wav_file(self, wav_path: str) -> Optional[PerceptionEvent]:
        """Reads a WAV file from disk, extracts PCM, and transcribes."""
        try:
            with wave.open(wav_path, "rb") as wf:
                sr = wf.getframerate()
                n_frames = wf.getnframes()
                frames = wf.readframes(n_frames)
                audio_arr = np.frombuffer(frames, dtype=np.int16)
                return self.process_buffer(audio_arr, samplerate=sr)
        except Exception as e:
            logger.error("[SpeechProcessor] Failed reading WAV file %s: %s", wav_path, str(e))
            return None


speech_processor = SpeechProcessor()
