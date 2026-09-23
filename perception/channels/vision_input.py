"""Vision Input Channel for JARVIS.

Captures screen frames (desktop display) and camera frames (webcam),
with graceful degradation if camera hardware is missing.
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path
import numpy as np
from PIL import Image, ImageGrab

from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Channels.Vision")


class VisionInputChannel:
    """Channel for capturing screen shots and webcam frames."""

    def capture_screen(self, bbox: Optional[tuple] = None) -> Optional[np.ndarray]:
        """Captures the current desktop screen frame as RGB numpy array."""
        try:
            screenshot = ImageGrab.grab(bbox=bbox)
            arr = np.array(screenshot)
            logger.debug("[VisionInputChannel] Captured screen: %s", arr.shape)
            return arr
        except Exception as e:
            logger.warning("[VisionInputChannel] Screen capture failed: %s", str(e))
            return None

    def capture_camera_frame(self, camera_index: int = 0) -> Optional[np.ndarray]:
        """Captures a single frame from the specified webcam device index."""
        try:
            import cv2
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                logger.warning("[VisionInputChannel] Camera index %d not accessible. Degrading gracefully.", camera_index)
                return None

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                logger.warning("[VisionInputChannel] Failed to retrieve frame from camera %d", camera_index)
                return None

            # Convert BGR from OpenCV to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return rgb_frame
        except Exception as e:
            logger.warning("[VisionInputChannel] Camera capture exception: %s", str(e))
            return None

    def ingest_image_file(self, file_path: str) -> Optional[np.ndarray]:
        """Loads an image from disk as an RGB numpy array."""
        p = Path(file_path)
        if not p.exists():
            logger.error("[VisionInputChannel] Image file not found: %s", file_path)
            return None
        try:
            with Image.open(p) as img:
                return np.array(img.convert("RGB"))
        except Exception as e:
            logger.error("[VisionInputChannel] Failed loading image %s: %s", file_path, str(e))
            return None

    def emit_frame_event(self, frame: np.ndarray, source_type: str = "screen") -> PerceptionEvent:
        """Publishes a vision_frame PerceptionEvent to the EventBus."""
        height, width = frame.shape[:2]
        channels = frame.shape[2] if len(frame.shape) > 2 else 1

        payload = {
            "source_type": source_type,
            "width": width,
            "height": height,
            "channels": channels,
            "frame_data": frame,
        }

        event = PerceptionEvent(
            type="vision_frame",
            payload=payload,
            source="vision_input",
            active_persona=settings.active_persona_name,
        )

        logger.debug("[VisionInputChannel] Emitted vision frame (%s, %dx%d)", source_type, width, height)
        event_bus.publish(event)
        return event


vision_input_channel = VisionInputChannel()
