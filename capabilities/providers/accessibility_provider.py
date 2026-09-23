"""Accessibility Capability Provider.

Supports:
- accessibility.format_payload: Formats rich visual and tabular outputs into screen-reader friendly descriptive text.
- accessibility.toggle_high_contrast: Toggles high-contrast HUD modes and simplified interaction styles.
"""

import logging
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult

logger = logging.getLogger("JARVIS.Providers.Accessibility")


class AccessibilityProvider(BaseCapabilityProvider):
    """Provides accessibility-aware payload transformations and UI mode configuration."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.ui.accessible_payload",
                name="Accessibility & Screen Reader Formatting Provider",
                supported_capabilities=[
                    "accessibility.format_payload",
                    "accessibility.toggle_high_contrast",
                ],
                priority=10,
                estimated_latency_ms=5.0,
            )
        )
        self.high_contrast_active = False

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            if capability == "accessibility.format_payload":
                raw_data = parameters.get("payload")
                if raw_data is None:
                    raw_data = parameters.get("table")
                if raw_data is None:
                    raw_data = parameters.get("data")
                if raw_data is None:
                    raw_data = parameters.get("text", {})

                # Converts complex nested telemetry, tabular, or conversational structures into linear screen-reader text
                lines = []
                if isinstance(raw_data, dict):
                    for k, v in raw_data.items():
                        clean_key = str(k).replace("_", " ").title()
                        lines.append(f"{clean_key}: {v}")
                elif isinstance(raw_data, list):
                    for idx, item in enumerate(raw_data, 1):
                        if isinstance(item, dict):
                            row_str = ", ".join(f"{str(k).replace('_', ' ').title()}: {v}" for k, v in item.items())
                            lines.append(f"Row {idx}: {row_str}")
                        else:
                            lines.append(f"Item {idx}: {item}")
                else:
                    text_str = str(raw_data).strip()
                    if text_str:
                        lines.append(text_str)

                accessible_text = ". ".join(lines) if lines else "No content available."
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                out = {
                    "accessible_text": accessible_text,
                    "aria_live": parameters.get("role", "polite"),
                    "screen_reader_ready": True,
                }
                return ActionResult(
                    status="SUCCESS",
                    output=out,
                    message=f"Payload transformed into screen-reader format ({len(accessible_text)} chars).",
                    execution_time_ms=elapsed,
                )

            elif capability == "accessibility.toggle_high_contrast":
                enable = parameters.get("enable")
                if enable is None:
                    self.high_contrast_active = not self.high_contrast_active
                else:
                    self.high_contrast_active = bool(enable)

                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                out = {
                    "high_contrast_mode": self.high_contrast_active,
                    "theme": "dark_high_contrast" if self.high_contrast_active else "standard_jarvis",
                }
                msg = f"High-contrast accessibility mode set to: {self.high_contrast_active}."
                return ActionResult(status="SUCCESS", output=out, message=msg, execution_time_ms=elapsed)

            else:
                elapsed = (time.perf_counter() - t_start) * 1000
                return ActionResult(
                    status="FAILED",
                    output=None,
                    message=f"Unsupported accessibility capability: {capability}",
                    execution_time_ms=elapsed,
                )

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)
