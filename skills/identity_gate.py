"""Identity Gate Skill for JARVIS using local OpenCV face detection.

Free, local visual authentication gate before executing privileged commands.
Zero external API calls.
"""

import logging
from typing import Dict, Any
from pathlib import Path
from config.settings import settings, PROJECT_ROOT

logger = logging.getLogger("JARVIS.Skills.Identity")

KNOWN_FACES_DIR = PROJECT_ROOT / "models" / "faces"
KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)


class IdentityGateSkill:
    def __init__(self):
        self.enabled = settings.integrations.get("identity_gate", {}).get("enabled", True)
        self._classifier = None

    def _get_classifier(self):
        if self._classifier is not None:
            return self._classifier

        try:
            import cv2
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._classifier = cv2.CascadeClassifier(cascade_path)
            return self._classifier
        except Exception as e:
            logger.warning("[Identity Gate] Could not load Haar cascade: %s", str(e))
            return None

    def verify_face_presence(self, camera_index: int = 0) -> Dict[str, Any]:
        """Captures a single frame from the camera and verifies face presence."""
        if not self.enabled:
            return {"verified": True, "bypassed": True, "reason": "Identity gate disabled in config"}

        try:
            import cv2
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                logger.warning("[Identity Gate] Camera index %d not accessible; degrading to bypass mode", camera_index)
                return {"verified": True, "bypassed": True, "reason": "Camera not detected"}

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                return {"verified": False, "error": "Failed to capture video frame"}

            classifier = self._get_classifier()
            if not classifier:
                return {"verified": True, "bypassed": True, "reason": "Classifier unavailable"}

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = classifier.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))

            if len(faces) > 0:
                logger.info("[Identity Gate] Verified user presence (%d face(s) detected)", len(faces))
                return {"verified": True, "faces_detected": len(faces)}
            else:
                logger.warning("[Identity Gate] No face detected in frame")
                return {"verified": False, "faces_detected": 0}
        except Exception as e:
            logger.error("[Identity Gate Error] %s", str(e))
            return {"verified": False, "error": str(e)}


identity_gate = IdentityGateSkill()
