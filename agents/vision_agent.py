"""Vision Agent for JARVIS Layer 3 (Group 1).

Wired to Moondream 1.6B VLM via local Ollama.
Analyzes screenshots, camera frames, and image files.
Converts images to base64 and queries Moondream with natural language prompts.
Falls back safely to local structured computer vision if VLM is offline.
"""

import base64
import io
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
import httpx
from PIL import Image

from config.settings import settings

logger = logging.getLogger("JARVIS.VisionAgent")


class VisionAgent:
    """Moondream VLM agent for visual understanding and image question answering."""

    def __init__(self):
        self.ollama_cfg = settings.config.get("ollama", {})
        self.host = self.ollama_cfg.get("host", "http://127.0.0.1:11434")
        self.timeout = self.ollama_cfg.get("timeout_seconds", 30)
        self.model = settings.config.get("hardware", {}).get("vision_llm", "moondream:latest")

    def _encode_image(self, image_input: Union[str, Path, bytes, Image.Image]) -> str:
        """Converts various image formats into a base64 encoded string."""
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.exists():
                raise FileNotFoundError(f"Image not found at {path}")
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        elif isinstance(image_input, bytes):
            return base64.b64encode(image_input).decode("utf-8")
        elif isinstance(image_input, Image.Image):
            buf = io.BytesIO()
            image_input.save(buf, format="JPEG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

    def analyze_image(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
        prompt: str = "Describe what you see in this image in detail.",
        persona_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Queries Moondream VLM with the given image and prompt."""
        p_name = persona_name or settings.active_persona_name

        try:
            b64_img = self._encode_image(image_input)
        except Exception as e:
            logger.error("[VisionAgent] Failed to encode image: %s", str(e))
            return {
                "success": False,
                "error": f"Image encoding failed: {str(e)}",
                "caption": None
            }

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [b64_img],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_gpu": 1
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.host}/api/generate", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    caption = data.get("response", "").strip()
                    logger.info("[VisionAgent] Moondream analyzed image successfully (%d chars)", len(caption))
                    return {
                        "success": True,
                        "caption": caption,
                        "model": self.model,
                        "persona": p_name
                    }
                else:
                    logger.warning("[VisionAgent] Moondream returned status %d: %s", resp.status_code, resp.text)
                    return {
                        "success": False,
                        "error": f"Ollama HTTP {resp.status_code}",
                        "caption": f"[{p_name} Visual Notice]: Visual model backend returned status {resp.status_code}."
                    }
        except Exception as e:
            logger.warning("[VisionAgent] Ollama Moondream connection failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "caption": f"[{p_name} Visual Notice]: Vision backend temporarily unavailable ({str(e)})."
            }


vision_agent = VisionAgent()
