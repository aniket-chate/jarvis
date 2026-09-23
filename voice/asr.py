"""Automatic Speech Recognition (ASR) Engine for JARVIS (CPU only).

Uses Whisper (base/small model) running strictly on CPU via CTranslate2.
Zero VRAM consumption — keeps GPU headroom reserved for Qwen2.5 3B / Moondream.
"""

import logging
import io
import wave
from typing import Optional
import numpy as np
from config.settings import settings

logger = logging.getLogger("JARVIS.ASR")


class ASREngine:
    def __init__(self):
        self.model_size = settings.voice.get("whisper_model", "base")
        self.device = "cpu"
        self.compute_type = "int8"
        self._model = None

    def _ensure_model_loaded(self) -> bool:
        """Loads Whisper CPU model on demand."""
        if self._model is not None:
            return True

        try:
            from faster_whisper import WhisperModel
            logger.info("Loading Whisper ASR model '%s' on CPU (int8)...", self.model_size)
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=4,
            )
            logger.info("Whisper ASR '%s' ready on CPU.", self.model_size)
            return True
        except Exception as e:
            logger.error("[ASR Error] Failed to load Whisper model: %s", str(e))
            return False

    def transcribe_audio_buffer(self, audio_data: np.ndarray, samplerate: int = 16000, language: Optional[str] = None) -> str:
        """Transcribes a raw audio buffer (16kHz float32 or int16 numpy array) with language routing."""
        if not self._ensure_model_loaded():
            return ""

        try:
            # Ensure float32 normalized in [-1.0, 1.0]
            if audio_data.dtype == np.int16:
                audio_float = audio_data.astype(np.float32) / 32768.0
            else:
                audio_float = audio_data.astype(np.float32)

            lang_param = language if (language and language.lower() != "auto") else None
            segments, info = self._model.transcribe(
                audio_float,
                beam_size=1,
                language=lang_param,
                vad_filter=True,
            )

            text_segments = [s.text.strip() for s in segments if s.text.strip()]
            full_text = " ".join(text_segments).strip()
            if full_text:
                logger.info("[ASR Result] Transcribed: '%s'", full_text)
            return full_text
        except Exception as e:
            logger.error("[ASR Transcription Error] %s", str(e))
            return ""


# Global singleton instance
asr_engine = ASREngine()
