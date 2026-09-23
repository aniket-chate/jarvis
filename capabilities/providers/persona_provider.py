"""Persona & Social Interaction Capability Provider.

Supports:
- system.switch_persona: Hot-swaps the active persona (Jarvis, Friday, Ultron, Omi).
- system.set_tone: Dynamically configures tone/style modifiers (sardonic, warm, concise, formal).
- system.get_persona: Retrieves the current active persona identity, tone, and system prompt.
"""

import logging
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from config.settings import settings
from llm.personas import get_system_prompt

logger = logging.getLogger("JARVIS.Providers.Persona")


class PersonaManagerProvider(BaseCapabilityProvider):
    """Provides hot-swappable persona and conversational tone management."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.llm.persona_manager",
                name="Persona & Social Interaction Manager",
                supported_capabilities=[
                    "system.switch_persona",
                    "system.set_tone",
                    "system.get_persona",
                ],
                priority=10,
                estimated_latency_ms=2.0,
            )
        )
        self._active_tone_modifier: Optional[str] = None

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            if capability == "system.switch_persona":
                target_p = parameters.get("persona") or parameters.get("name") or "Jarvis"
                settings.set_active_persona(target_p)
                p_cfg = settings.get_persona()
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                out = {
                    "active_persona": p_cfg.name,
                    "tone": p_cfg.tone,
                    "voice": getattr(p_cfg, "voice", "en_GB-alan-medium"),
                }
                msg = f"Persona switched to '{p_cfg.name}' (Tone: {p_cfg.tone})."
                return ActionResult(status="SUCCESS", output=out, message=msg, execution_time_ms=elapsed)

            elif capability == "system.set_tone":
                tone = parameters.get("tone", "neutral")
                self._active_tone_modifier = tone
                p_cfg = settings.get_persona()
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                out = {
                    "persona": p_cfg.name,
                    "base_tone": p_cfg.tone,
                    "active_tone_modifier": self._active_tone_modifier,
                }
                msg = f"Tone modifier for '{p_cfg.name}' updated to '{tone}'."
                return ActionResult(status="SUCCESS", output=out, message=msg, execution_time_ms=elapsed)

            elif capability == "system.get_persona":
                p_cfg = settings.get_persona()
                prompt_snippet = get_system_prompt(p_cfg.name)[:120] + "..."
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                out = {
                    "active_persona": p_cfg.name,
                    "tone": p_cfg.tone,
                    "voice_profile": getattr(p_cfg, "voice", "en_GB-alan-medium"),
                    "tone_modifier": self._active_tone_modifier,
                    "system_prompt_preview": prompt_snippet,
                }
                msg = f"Active persona: {p_cfg.name} ({p_cfg.tone})."
                return ActionResult(status="SUCCESS", output=out, message=msg, execution_time_ms=elapsed)

            else:
                elapsed = (time.perf_counter() - t_start) * 1000
                return ActionResult(status="FAILED", output=None, message=f"Unsupported persona capability: {capability}", execution_time_ms=elapsed)

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)
