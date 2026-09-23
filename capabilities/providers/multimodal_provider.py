"""Multimodal Understanding Capability Provider.

Supports:
- multimodal.fuse: Fuses vision, audio, screen, and text streams into a unified perception event.
- multimodal.resolve_conflict: Explicitly resolves discrepancies between modalities (e.g. Vision vs World Model)
  using timestamp freshness and active empirical reality probes.
"""

import logging
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from cognitive.world_model import world_model

logger = logging.getLogger("JARVIS.Providers.Multimodal")


class MultimodalUnderstandingProvider(BaseCapabilityProvider):
    """Fuses multi-sensory perceptions and resolves inter-modality discrepancies."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.multimodal.fused_engine",
                name="Multimodal Fusion & Conflict Resolution Engine",
                supported_capabilities=[
                    "multimodal.fuse",
                    "multimodal.resolve_conflict",
                ],
                priority=10,
                estimated_latency_ms=80.0,
            )
        )

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            if capability == "multimodal.fuse":
                text_input = parameters.get("text")
                vision_input = parameters.get("vision")
                audio_input = parameters.get("audio")
                env_state = world_model.get_context_snapshot()

                fused_payload = {
                    "text": text_input,
                    "visual_summary": vision_input.get("caption") if isinstance(vision_input, dict) else str(vision_input),
                    "audio_transcript": audio_input.get("text") if isinstance(audio_input, dict) else str(audio_input),
                    "active_window": env_state.get("active_window"),
                    "active_browser": env_state.get("active_browser"),
                    "timestamp": time.time(),
                }
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                return ActionResult(
                    status="SUCCESS",
                    output=fused_payload,
                    message="Multimodal inputs fused cleanly into unified perception frame.",
                    execution_time_ms=elapsed,
                )

            elif capability == "multimodal.resolve_conflict":
                # Discrepancy example: Vision claims application is open, World Model claims closed
                modality_a = parameters.get("modality_a", {})  # e.g., {"source": "vision", "claim": "open", "timestamp": time.time() - 2}
                modality_b = parameters.get("modality_b", {})  # e.g., {"source": "world_model", "claim": "closed", "timestamp": time.time() - 10}
                entity = parameters.get("entity", "chrome")

                t_a = modality_a.get("timestamp", 0)
                t_b = modality_b.get("timestamp", 0)

                # 1. Freshness check
                if abs(t_a - t_b) > 5.0:
                    fresher = modality_a if t_a > t_b else modality_b
                    resolved_claim = fresher.get("claim")
                    resolution_method = f"Freshness comparison: '{fresher.get('source')}' was {abs(t_a - t_b):.1f}s more recent."
                else:
                    # 2. Ambiguity: Timestamps are close -> Trigger live empirical reality probe!
                    probe_result = world_model.probe_process(entity)
                    is_active = bool(probe_result.get("is_running", probe_result.get("running", False)))
                    resolved_claim = "open" if is_active else "closed"
                    resolution_method = f"Live empirical probe of process '{entity}' determined ground truth: {resolved_claim}."

                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                out = {
                    "entity": entity,
                    "resolved_state": resolved_claim,
                    "resolution_method": resolution_method,
                    "confidence": 0.96,
                }
                msg = f"Resolved conflict for '{entity}': state is '{resolved_claim}' ({resolution_method})"
                return ActionResult(status="SUCCESS", output=out, message=msg, execution_time_ms=elapsed)

            else:
                elapsed = (time.perf_counter() - t_start) * 1000
                return ActionResult(
                    status="FAILED",
                    output=None,
                    message=f"Unsupported multimodal capability: {capability}",
                    execution_time_ms=elapsed,
                )

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)
