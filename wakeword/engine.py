"""Multi-Persona Wake-Word Engine for JARVIS using openWakeWord (CPU only).

Loads custom trained models (jarvis.onnx, friday.onnx, ultron.onnx, omi.onnx)
simultaneously if present in models/wakewords/. Whichever one fires sets the active
persona for that session.

If custom models are not yet on disk (e.g. being trained), falls back cleanly to
the built-in development model ('hey_jarvis') to allow uninterrupted development
without generating dummy or placeholder files.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import openwakeword
from openwakeword.model import Model
from config.settings import settings, PROJECT_ROOT

logger = logging.getLogger("JARVIS.WakeWord")


class MultiPersonaWakeWordEngine:
    def __init__(self):
        self.models_dir = PROJECT_ROOT / "models" / "wakewords"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.model: Optional[Model] = None
        self.active_models: Dict[str, str] = {}  # model_key -> persona_name
        self.is_fallback = False
        self.threshold = 0.5
        self.load_models()

    def load_models(self) -> None:
        """Discovers available ONNX models or defaults to temporary dev model."""
        self.active_models.clear()

        # Map expected models to persona names
        target_models = {
            "jarvis.onnx": "Jarvis",
            "friday.onnx": "Friday",
            "ultron.onnx": "Ultron",
            "omi.onnx": "Omi",
        }

        found_paths: List[str] = []
        for filename, persona_name in target_models.items():
            model_path = self.models_dir / filename
            if model_path.exists() and model_path.stat().st_size > 0:
                found_paths.append(str(model_path))
                # openwakeword model key is typically the file stem
                stem = model_path.stem
                self.active_models[stem] = persona_name
                logger.info("Registered custom wake-word model for %s: %s", persona_name, filename)

        if found_paths:
            logger.info("Initializing multi-persona detector with %d custom ONNX models (CPU only)", len(found_paths))
            try:
                self.model = Model(
                    wakeword_models=found_paths,
                    inference_framework="onnx",
                )
                self.is_fallback = False
                return
            except Exception as e:
                logger.error("Failed to load custom ONNX models: %s; falling back to development engine", str(e))

        # Fallback to built-in openWakeWord model for development
        self.is_fallback = True
        logger.info(
            "[WakeWord Development Fallback] Custom models not yet placed in models/wakewords/. "
            "Loading built-in 'hey_jarvis' model. Drop trained ONNX files into %s to activate.",
            self.models_dir,
        )
        try:
            self.model = Model(
                wakeword_models=["hey_jarvis"],
                inference_framework="onnx",
            )
            self.active_models["hey_jarvis"] = "Jarvis"
        except Exception as e:
            logger.error("Failed to load fallback wake word: %s", str(e))
            self.model = None

    def process_audio_frame(self, audio_chunk: np.ndarray) -> Optional[Tuple[str, float]]:
        """Processes 16kHz mono 16-bit PCM audio frame (1280 samples / 80ms).

        Returns (persona_name, score) if a wake word triggers, otherwise None.
        """
        if not self.model:
            return None

        # Predict scores
        prediction = self.model.predict(audio_chunk)

        for model_key, score in prediction.items():
            if score >= self.threshold:
                persona_name = self.active_models.get(model_key, "Jarvis")
                logger.info(
                    "Wake word TRIGGERED! Detected: '%s' (score: %.3f) -> Switching persona to: %s",
                    model_key,
                    score,
                    persona_name,
                )
                settings.set_active_persona(persona_name)
                # Reset model buffer
                self.model.reset()
                return (persona_name, float(score))

        return None

    def reload(self) -> None:
        """Hot-reloads wake word models without restarting JARVIS."""
        logger.info("Reloading wake-word engine from disk...")
        self.load_models()
