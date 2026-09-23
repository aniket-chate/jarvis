"""Image Generation Agent for JARVIS Layer 3 (Group 2).

Documented stub / optional provider for local Stable Diffusion or free hosted options.
Per specification: Built as documented stub unless explicitly requested,
preserving the 4GB VRAM hardware budget for Core LLM + Vision.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.ImageGenAgent")


class ImageGenAgent:
    """Agent for image generation via local Stable Diffusion or free hosted API."""

    def __init__(self):
        self.enabled = False  # Disabled by default to protect 4GB VRAM target

    def generate_image(self, prompt: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Documented stub for image generation."""
        logger.info("[ImageGenAgent] Request received for prompt: '%s'", prompt)
        return {
            "success": False,
            "status": "stub_mode",
            "prompt": prompt,
            "message": (
                "Image generation is currently configured as a documented stub to preserve "
                "the 4GB VRAM hardware budget for Qwen2.5 3B Core LLM and Moondream 1.6B VLM. "
                "Can be enabled by connecting a local Stable Diffusion / ComfyUI endpoint "
                "or free hosted Pollinations/HuggingFace API in config/config.yaml."
            )
        }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        prompt = inputs.get("prompt", "a futuristic digital assistant interface")
        return self.generate_image(prompt=prompt, output_path=inputs.get("output_path"))


image_gen_agent = ImageGenAgent()
