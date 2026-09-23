"""JARVIS Observability & Distributed Cognitive Tracing.

Reconstructs the full cognitive narrative across the entire pipeline:
"What did JARVIS think was happening?" -> Understanding
"Why?" -> Reasoning
"What was the goal?" -> Goal Engine
"What did it plan?" -> Planning Engine
"Which capability did it select?" -> Capability Intelligence
"What policy decision was made?" -> Policy/Safety Kernel
"What action happened?" -> Execution & Action Fabric
"What actually changed?" -> Observation
"Was it verified?" -> Verification
"What did JARVIS learn?" -> Experience & Learning
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger("JARVIS.Observability.Tracer")


@dataclass
class TraceSpan:
    span_id: str
    request_id: str
    stage: str               # "understanding", "reasoning", "goal", "plan", "capability", "policy", "execution", "observation", "verification", "learning"
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveTrace:
    request_id: str
    created_at: float = field(default_factory=time.time)
    spans: List[TraceSpan] = field(default_factory=list)

    def add_span(self, span: TraceSpan):
        self.spans.append(span)

    def reconstruct_narrative(self) -> Dict[str, Any]:
        """Reconstructs the complete cognitive explanation for this request."""
        narrative = {
            "request_id": self.request_id,
            "what_jarvis_understood": None,
            "why_reasoning": None,
            "goal_formulated": None,
            "plan_synthesized": None,
            "capability_selected": None,
            "policy_decision": None,
            "action_executed": None,
            "world_change_observed": None,
            "verification_outcome": None,
            "learning_outcome": None,
        }
        for s in self.spans:
            if s.stage == "understanding":
                narrative["what_jarvis_understood"] = s.outputs
            elif s.stage == "reasoning":
                narrative["why_reasoning"] = s.outputs.get("deduction")
            elif s.stage == "goal":
                narrative["goal_formulated"] = s.outputs.get("goal")
            elif s.stage == "plan":
                narrative["plan_synthesized"] = s.outputs.get("steps")
            elif s.stage == "capability":
                narrative["capability_selected"] = s.outputs.get("provider")
            elif s.stage == "policy":
                narrative["policy_decision"] = s.outputs.get("level")
            elif s.stage == "execution":
                narrative["action_executed"] = s.outputs.get("action")
            elif s.stage == "observation":
                narrative["world_change_observed"] = s.outputs.get("observed")
            elif s.stage == "verification":
                narrative["verification_outcome"] = s.outputs.get("status")
            elif s.stage == "learning":
                narrative["learning_outcome"] = s.outputs.get("reward")

        return narrative


class CognitiveTracer:
    """Manages active distributed cognitive traces correlated by request_id."""

    def __init__(self, trace_dir: Optional[Path] = None):
        self.trace_dir = trace_dir or Path(r"d:\assignment\JARVIS\logs\traces")
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._active_traces: Dict[str, CognitiveTrace] = {}

    def start_trace(self, request_id: str) -> CognitiveTrace:
        trace = CognitiveTrace(request_id=request_id)
        self._active_traces[request_id] = trace
        return trace

    def record_span(
        self,
        request_id: str,
        stage: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        trace = self._active_traces.get(request_id)
        if not trace:
            trace = self.start_trace(request_id)

        now = time.time()
        span = TraceSpan(
            span_id=f"span_{uuid.uuid4().hex[:8]}",
            request_id=request_id,
            stage=stage,
            start_time=now - (duration_ms / 1000.0),
            end_time=now,
            duration_ms=duration_ms,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata or {},
        )
        trace.add_span(span)
        logger.debug("[CognitiveTracer] Recorded span '%s' for request '%s' (dur=%.1fms)", stage, request_id, duration_ms)

    def get_narrative(self, request_id: str) -> Optional[Dict[str, Any]]:
        trace = self._active_traces.get(request_id)
        return trace.reconstruct_narrative() if trace else None


# Master Cognitive Tracer singleton
cognitive_tracer = CognitiveTracer()
