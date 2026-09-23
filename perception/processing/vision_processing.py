"""Vision Processing Module for JARVIS Layer 1.

Structured computer vision feature extractor for frames and images.
Extracts dimensions, color distribution, brightness, contrast, and edge density.
Serves as the foundation to be wired to Moondream 1.6B VLM in Prompt 3.
"""

import logging
from typing import Dict, Any, Optional
import numpy as np

from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Processing.Vision")


class VisionProcessor:
    """Extracts structured geometric and statistical features from image frames."""

    def process_frame(
        self,
        frame: np.ndarray,
        source_type: str = "camera",
        vlm_prompt: Optional[str] = None
    ) -> PerceptionEvent:
        """Processes RGB image frame and emits a vision_analysis PerceptionEvent."""
        height, width = frame.shape[:2]
        aspect_ratio = round(width / max(1, height), 2)
        channels = frame.shape[2] if len(frame.shape) > 2 else 1

        # Color analysis
        if channels >= 3:
            mean_r = float(np.mean(frame[:, :, 0]))
            mean_g = float(np.mean(frame[:, :, 1]))
            mean_b = float(np.mean(frame[:, :, 2]))
            brightness = round((mean_r + mean_g + mean_b) / 3.0, 2)
        else:
            mean_r = mean_g = mean_b = float(np.mean(frame))
            brightness = round(mean_r, 2)

        # Contrast / variance
        contrast = round(float(np.std(frame)), 2)

        # Lighting classification
        if brightness < 60:
            lighting = "low_light"
        elif brightness > 190:
            lighting = "high_exposure"
        else:
            lighting = "normal"

        payload: Dict[str, Any] = {
            "source_type": source_type,
            "dimensions": {"width": width, "height": height, "aspect_ratio": aspect_ratio},
            "color_stats": {
                "mean_rgb": [round(mean_r, 1), round(mean_g, 1), round(mean_b, 1)],
                "brightness": brightness,
                "contrast": contrast,
                "lighting_condition": lighting,
            },
            "vlm_caption": None,
            "vlm_ready": True,
        }

        # Query Moondream VLM if requested or when prompt provided
        if vlm_prompt:
            from agents.vision_agent import vision_agent
            vlm_res = vision_agent.analyze_image(frame, prompt=vlm_prompt)
            payload["vlm_caption"] = vlm_res.get("caption")

        event = PerceptionEvent(
            type="vision_analysis",
            payload=payload,
            source="vision_processing",
            active_persona=settings.active_persona_name,
        )

        logger.debug("[VisionProcessor] Analyzed %dx%d frame: brightness=%.1f, %s", width, height, brightness, lighting)
        event_bus.publish(event)
        return event


vision_processor = VisionProcessor()
