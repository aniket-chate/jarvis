"""Emotion & Social Context Capability Provider.

Supports:
- emotion.analyze_sentiment: Evaluates probabilistic sentiment cues without claiming absolute certainty.
- emotion.detect_urgency: Evaluates conversational urgency and selects empathetic, persona-aligned response tones.
"""

import logging
import re
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult

logger = logging.getLogger("JARVIS.Providers.Emotion")


class EmotionSocialContextProvider(BaseCapabilityProvider):
    """Provides probabilistic conversational emotion and urgency analysis."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.perception.sentiment",
                name="Probabilistic Emotion & Social Context Provider",
                supported_capabilities=[
                    "emotion.analyze_sentiment",
                    "emotion.detect_urgency",
                ],
                priority=10,
                estimated_latency_ms=10.0,
            )
        )

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            text = (parameters.get("text") or parameters.get("utterance") or "").lower()

            if capability == "emotion.analyze_sentiment":
                # Probabilistic assessment based on sentiment cues
                positive_cues = ["great", "awesome", "perfect", "thanks", "thank you", "nice", "excellent", "love it"]
                negative_cues = ["frustrated", "broken", "annoying", "terrible", "bad", "hate", "stuck", "useless"]
                
                pos_count = sum(1 for c in positive_cues if c in text)
                neg_count = sum(1 for c in negative_cues if c in text)
                
                if pos_count > neg_count:
                    sentiment = "positive"
                    conf = min(0.90, 0.60 + 0.10 * pos_count)
                elif neg_count > pos_count:
                    sentiment = "frustrated"
                    conf = min(0.88, 0.58 + 0.10 * neg_count)
                else:
                    sentiment = "neutral"
                    conf = 0.85

                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                out = {
                    "sentiment_category": sentiment,
                    "confidence": conf,
                    "probabilistic_claim": True,
                    "recommended_tone": "empathetic_helpful" if sentiment == "frustrated" else "efficient_courteous",
                }
                msg = f"Probabilistic sentiment: '{sentiment}' (confidence: {conf:.2f})."
                return ActionResult(status="SUCCESS", output=out, message=msg, execution_time_ms=elapsed)

            elif capability == "emotion.detect_urgency":
                urgent_cues = ["urgent", "immediately", "asap", "emergency", "hurry", "critical", "now"]
                is_urgent = any(c in text for c in urgent_cues) or bool(parameters.get("forced_urgent", False))
                conf = 0.92 if is_urgent else 0.88
                
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                out = {
                    "is_urgent": is_urgent,
                    "confidence": conf,
                    "priority_boost": 2 if is_urgent else 0,
                }
                msg = "High urgency detected: Elevating task priority." if is_urgent else "Standard conversational cadence."
                return ActionResult(status="SUCCESS", output=out, message=msg, execution_time_ms=elapsed)

            else:
                elapsed = (time.perf_counter() - t_start) * 1000
                return ActionResult(
                    status="FAILED",
                    output=None,
                    message=f"Unsupported emotion capability: {capability}",
                    execution_time_ms=elapsed,
                )

        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)
