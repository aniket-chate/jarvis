"""Chromecast / Google Cast Skill for JARVIS.

Discovers local Google Cast devices (Chromecast, Google TV, Nest Hub) and casts media URLs.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger("JARVIS.Skills.Cast")


class CastSkill:
    def __init__(self):
        self._chromecasts = []
        self._browser = None

    def discover_devices(self, timeout: int = 4) -> List[str]:
        """Discovers available Google Cast devices on the local subnet."""
        try:
            import pychromecast
            chromecasts, browser = pychromecast.get_listed_chromecasts(
                friendly_names=[],
                discovery_timeout=timeout,
            )
            self._chromecasts = chromecasts
            self._browser = browser
            device_names = [cc.name for cc in chromecasts]
            logger.info("[Cast Discovery] Discovered %d devices: %s", len(device_names), device_names)
            return device_names
        except Exception as e:
            logger.warning("[Cast Discovery Error] %s", str(e))
            return []

    def cast_media(self, device_name: str, media_url: str, content_type: str = "video/mp4") -> Dict[str, Any]:
        """Plays media URL on specified Chromecast device."""
        if not device_name or not device_name.strip():
            return {"success": False, "error": "Target device name cannot be empty."}
        try:
            try:
                import pychromecast
            except ImportError:
                return {
                    "success": False,
                    "error": "Chromecast hardware requires 'pychromecast'. Target device not found in live peer mesh.",
                }

            if not self._chromecasts:
                self.discover_devices()


            target = next((cc for cc in self._chromecasts if cc.name.lower() == device_name.lower()), None)
            if not target:
                return {
                    "success": False,
                    "error": f"Device '{device_name}' not found on local network.",
                }

            target.wait()
            mc = target.media_controller
            mc.play_media(media_url, content_type)
            mc.block_until_active()
            return {
                "success": True,
                "device": target.name,
                "media_url": media_url,
                "status": "playing",
            }
        except Exception as e:
            logger.error("[Cast Error] %s", str(e))
            return {"success": False, "error": str(e)}


cast_skill = CastSkill()
