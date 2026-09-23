"""Neural TTS Engine for JARVIS using Piper (CPU only).

Provides distinct voice profiles per persona using lightweight ONNX neural models.
Hardware target: CPU execution only — zero VRAM consumption.
Fallback: pyttsx3 is kept strictly as a temporary development/offline fallback
if a persona's Piper voice ONNX model has not yet been fetched.
"""

import io
import logging
import wave
from pathlib import Path
from typing import Optional

try:
    import sounddevice as sd
except ImportError:
    sd = None

import numpy as np

from config.settings import settings, PROJECT_ROOT

logger = logging.getLogger("JARVIS.TTS")

PIPER_VOICES_DIR = PROJECT_ROOT / "models" / "piper"
PIPER_VOICES_DIR.mkdir(parents=True, exist_ok=True)

# Default voice mappings per persona
PERSONA_VOICES = {
    "jarvis": "en_GB-alan-medium",
    "friday": "en_US-amy-medium",
    "ultron": "en_US-lessac-medium",
    "omi": "en_US-ryan-medium",
}


class PiperTTSEngine:
    def __init__(self):
        self.models_dir = PIPER_VOICES_DIR
        self._piper_voice = None
        self._current_voice_name: Optional[str] = None
        self._voice_cache: Dict[str, Any] = {}
        self._pyttsx3_engine = None

    def _init_pyttsx3_fallback(self):
        """Initializes pyttsx3 strictly as a fallback engine."""
        if self._pyttsx3_engine is None:
            try:
                import pyttsx3
                self._pyttsx3_engine = pyttsx3.init()
                self._pyttsx3_engine.setProperty("rate", 175)
                logger.info("[TTS Fallback] Initialized pyttsx3 fallback engine")
            except Exception as e:
                logger.error("[TTS Fallback] Could not initialize pyttsx3: %s", str(e))

    def _load_piper_voice(self, voice_name: str) -> bool:
        """Loads a Piper ONNX voice from models/piper/ with persistent in-memory caching."""
        if voice_name in self._voice_cache:
            self._piper_voice = self._voice_cache[voice_name]
            self._current_voice_name = voice_name
            return True

        onnx_path = self.models_dir / f"{voice_name}.onnx"
        config_path = self.models_dir / f"{voice_name}.onnx.json"

        resolved_name = voice_name
        if not (onnx_path.exists() and config_path.exists()):
            # Find any available .onnx voice in models/piper
            available_onnx = list(self.models_dir.glob("*.onnx"))
            if available_onnx:
                onnx_path = available_onnx[0]
                config_path = onnx_path.with_suffix(".onnx.json")
                resolved_name = onnx_path.stem

        # Check if resolved voice is already cached
        if resolved_name in self._voice_cache:
            voice_inst = self._voice_cache[resolved_name]
            self._voice_cache[voice_name] = voice_inst
            self._piper_voice = voice_inst
            self._current_voice_name = voice_name
            return True

        if onnx_path.exists() and config_path.exists():
            try:
                from piper import PiperVoice
                voice_inst = PiperVoice.load(str(onnx_path), config_path=str(config_path))
                self._voice_cache[resolved_name] = voice_inst
                self._voice_cache[voice_name] = voice_inst
                self._piper_voice = voice_inst
                self._current_voice_name = voice_name
                logger.info("[Piper TTS] Successfully loaded persistent neural voice: %s -> %s (CPU)", voice_name, resolved_name)
                return True
            except Exception as e:
                logger.error("[Piper TTS] Failed loading %s: %s", voice_name, str(e))
                self._piper_voice = None
                return False
        return False

    def synthesize_to_wav_bytes(self, text: str, persona_name: Optional[str] = None) -> Optional[bytes]:
        """Synthesizes text directly into an in-memory WAV byte buffer (zero disk I/O)."""
        if not text or not text.strip():
            return None

        persona = (persona_name or settings.active_persona_name).lower()
        target_voice = PERSONA_VOICES.get(persona, "en_US-lessac-medium")
        if self._current_voice_name != target_voice or not self._piper_voice:
            self._load_piper_voice(target_voice)

        if not self._piper_voice:
            return None

        # Distinct acoustic profiles per persona with natural cadence and native sample rate
        try:
            from piper.config import SynthesisConfig
            if persona == "friday":
                # Clear, responsive cadence with slight warmth, no resampling jitter
                syn_cfg = SynthesisConfig(length_scale=0.95, noise_scale=0.667, noise_w_scale=0.8)
            elif persona == "ultron":
                # Deliberate, menacingly measured cadence
                syn_cfg = SynthesisConfig(length_scale=1.12, noise_scale=0.60, noise_w_scale=0.75)
            elif persona == "omi":
                # Calm, gentle, concise cadence
                syn_cfg = SynthesisConfig(length_scale=1.02, noise_scale=0.667, noise_w_scale=0.8)
            else:  # Jarvis
                # Classic crisp, balanced cadence
                syn_cfg = SynthesisConfig(length_scale=1.00, noise_scale=0.667, noise_w_scale=0.80)
        except Exception:
            syn_cfg = None

        try:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav_file:
                params_set = False
                chunks = self._piper_voice.synthesize(text, syn_config=syn_cfg) if syn_cfg else self._piper_voice.synthesize(text)
                for chunk in chunks:
                    if not params_set:
                        wav_file.setnchannels(chunk.sample_channels)
                        wav_file.setsampwidth(chunk.sample_width)
                        wav_file.setframerate(chunk.sample_rate)
                        params_set = True
                    wav_file.writeframes(chunk.audio_int16_bytes)
            return buf.getvalue()
        except Exception as e:
            logger.error("[Piper TTS Synthesis Error] %s", str(e))
            return None

    def synthesize_to_wav(self, text: str, output_path: Path, persona_name: Optional[str] = None) -> bool:
        """Synthesizes text and saves it directly to a WAV file."""
        wav_bytes = self.synthesize_to_wav_bytes(text, persona_name)
        if wav_bytes is None:
            return False

        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(wav_bytes)
            logger.info("[Piper TTS] Saved audio to %s", output_path)
            return True
        except Exception as e:
            logger.error("[Piper TTS Save Error] %s", str(e))
            return False

    def speak(self, text: str, persona_name: Optional[str] = None) -> None:
        """Synthesizes and speaks text using Piper CPU or fallback."""
        if not text or not text.strip():
            return

        persona = (persona_name or settings.active_persona_name).lower()
        target_voice = PERSONA_VOICES.get(persona, "en_US-lessac-medium")

        # Try loading target Piper voice if not already loaded
        if self._current_voice_name != target_voice or not self._piper_voice:
            self._load_piper_voice(target_voice)

        # 1. Primary: Piper CPU neural TTS
        if self._piper_voice:
            try:
                audio_arrays = []
                sr = 22050
                for chunk in self._piper_voice.synthesize(text):
                    sr = chunk.sample_rate
                    audio_arrays.append(chunk.audio_int16_array)
                if audio_arrays:
                    data = np.concatenate(audio_arrays)
                    sd.play(data, samplerate=sr)
                    sd.wait()
                return
            except Exception as e:
                logger.warning("[Piper TTS Playback Error] %s; falling back to pyttsx3", str(e))

        # 2. Graceful Fallback: pyttsx3
        logger.info(
            "[TTS Notice] Piper model '%s' not in models/piper/. Using pyttsx3 fallback for speech.",
            target_voice,
        )
        self._init_pyttsx3_fallback()
        if self._pyttsx3_engine:
            try:
                self._pyttsx3_engine.say(text)
                self._pyttsx3_engine.runAndWait()
            except Exception as e:
                logger.error("[TTS Fallback Error] %s", str(e))

    def stop(self) -> None:
        """Stops active sounddevice or pyttsx3 audio playback immediately (barge-in)."""
        try:
            if sd is not None:
                sd.stop()
            if self._pyttsx3_engine:
                self._pyttsx3_engine.stop()
            logger.info("[Piper TTS] Playback successfully stopped via barge-in interrupt.")
        except Exception as e:
            logger.warning("[Piper TTS] Playback stop warning: %s", str(e))


# Global singleton instance
tts_engine = PiperTTSEngine()
