"""JARVIS Capability Contract Schema.

Defines the formal machine-readable contract specification for all 50 JARVIS capability domains.
Enforces Phase C standards: inputs, outputs, operations, safety classification,
verification strategy, retry policy, and provider bindings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SafetyClassification(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    MODIFYING = "MODIFYING"
    DESTRUCTIVE = "DESTRUCTIVE"
    EXTERNAL_COMMUNICATION = "EXTERNAL_COMMUNICATION"
    PRIVILEGED = "PRIVILEGED"
    PHYSICAL = "PHYSICAL"


@dataclass
class CapabilityContract:
    """Formal specification for a JARVIS Capability Domain."""
    capability_id: str                   # e.g., "01_natural_language", "21_desktop_os"
    name: str                            # Human-readable name
    domain: str                          # Root routing domain: "browser", "os", "file", etc.
    version: str = "1.0.0"
    purpose: str = ""
    supported_operations: List[str] = field(default_factory=list)  # e.g., ["os.window_management"]
    
    # Required dependencies & context
    required_context: List[str] = field(default_factory=list)
    required_world_model_state: List[str] = field(default_factory=list)
    required_memory: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    # Provider bindings
    primary_provider_id: str = ""
    fallback_provider_id: Optional[str] = None
    provider_selection_rules: Dict[str, Any] = field(default_factory=dict)
    
    # Safety & Policy
    safety_classification: SafetyClassification = SafetyClassification.READ_ONLY
    permission_requirements: List[str] = field(default_factory=list)
    requires_two_gate_confirmation: bool = False
    
    # Verification & Observation
    verification_strategy: str = "EMPIRICAL_OBSERVATION"  # e.g., "WIN32_API", "FILE_HASH", "CDP_TAB_LIST"
    
    # Execution & Resilience
    failure_modes: List[str] = field(default_factory=list)
    retry_limit: int = 2
    timeout_sec: float = 30.0
    cancellation_supported: bool = True
    checkpoint_required: bool = False
    
    # Telemetry & Learning
    observability_keys: List[str] = field(default_factory=list)
    learning_signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "domain": self.domain,
            "version": self.version,
            "purpose": self.purpose,
            "supported_operations": self.supported_operations,
            "dependencies": self.dependencies,
            "primary_provider_id": self.primary_provider_id,
            "fallback_provider_id": self.fallback_provider_id,
            "safety_classification": self.safety_classification.value,
            "permission_requirements": self.permission_requirements,
            "requires_two_gate_confirmation": self.requires_two_gate_confirmation,
            "verification_strategy": self.verification_strategy,
            "timeout_sec": self.timeout_sec,
            "retry_limit": self.retry_limit,
            "checkpoint_required": self.checkpoint_required,
        }
